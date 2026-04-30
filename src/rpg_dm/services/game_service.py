from __future__ import annotations

from sqlalchemy.orm import Session

from ..config import Settings
from ..models import CampaignRecap, MemoryUpdate, Quest, Turn
from ..schemas import CampaignImportPayload, MessageRequest
from ..utils import decode_quest_state, encode_quest_state, utcnow
from .llm_service import LMStudioClient, MemoryExtractionError
from .memory_service import apply_world_delta
from .serialization import load_campaign, serialize_campaign

LEGACY_RECAP_NOTE_TITLE = "Сюжет — резюме (авто)"
RECAP_TURN_ROLE = "assistant"


class GameService:
    def __init__(self, session: Session, settings: Settings, llm_client: LMStudioClient) -> None:
        self.session = session
        self.settings = settings
        self.llm_client = llm_client

    def process_turn(self, campaign_id: int, payload: MessageRequest) -> dict:
        campaign = load_campaign(self.session, campaign_id)
        if campaign is None:
            raise ValueError("Кампания не найдена.")

        prompt_tokens = self.llm_client.estimate_narrative_prompt_tokens(
            campaign,
            payload.message,
            payload.dice_result,
        )

        self._advance_timed_quests(campaign)

        raw_assistant_message = self.llm_client.generate_narrative(
            campaign,
            payload.message,
            payload.dice_result,
        )
        assistant_message = self.llm_client.sanitize_narrative(raw_assistant_message)

        player_turn = Turn(
            campaign_id=campaign_id,
            role="user",
            content=payload.message.strip(),
            dice_result=payload.dice_result,
        )
        assistant_turn = Turn(
            campaign_id=campaign_id,
            role="assistant",
            content=assistant_message,
            model_name=campaign.model_id,
        )
        self.session.add_all([player_turn, assistant_turn])
        self.session.flush()

        memory_update = MemoryUpdate(
            campaign_id=campaign_id,
            assistant_turn_id=assistant_turn.id,
            status="pending",
        )
        self.session.add(memory_update)

        try:
            delta, raw_payload = self.llm_client.extract_world_delta(
                campaign,
                payload.message,
                payload.dice_result,
                raw_assistant_message,
            )
            apply_world_delta(self.session, campaign, delta, assistant_turn.id)
            memory_update.status = "applied"
            memory_update.raw_payload = raw_payload
        except MemoryExtractionError as exc:
            memory_update.status = "failed"
            memory_update.error_message = str(exc)
            memory_update.raw_payload = exc.raw_payload

        campaign.updated_at = utcnow()
        self.session.commit()

        self._maybe_update_story_recap(campaign_id, prompt_tokens=prompt_tokens)

        updated = load_campaign(self.session, campaign_id)
        if updated is None:
            raise ValueError("Кампания была потеряна после сохранения.")
        return serialize_campaign(updated)

    def import_transcript(self, campaign_id: int, payload: CampaignImportPayload) -> dict:
        campaign = load_campaign(self.session, campaign_id)
        if campaign is None:
            raise ValueError("Кампания не найдена.")

        memory_update = MemoryUpdate(
            campaign_id=campaign_id,
            status="pending",
            raw_payload=payload.transcript.strip(),
        )
        self.session.add(memory_update)
        self.session.flush()

        try:
            delta, raw_payload = self.llm_client.import_world_delta_from_transcript(campaign, payload.transcript)
            apply_world_delta(self.session, campaign, delta, assistant_turn_id=None)
            memory_update.status = "applied"
            memory_update.raw_payload = raw_payload
        except MemoryExtractionError as exc:
            memory_update.status = "failed"
            memory_update.error_message = str(exc)
            memory_update.raw_payload = exc.raw_payload or payload.transcript.strip()

        campaign.updated_at = utcnow()
        self.session.commit()

        if payload.show_chat_summary:
            # Imports can be huge. Build the recap only once, after the final chunk,
            # otherwise every chunk pays for an extra model call.
            recap_text = self._maybe_update_story_recap(campaign_id, force=True, prompt_tokens=0)
            self.session.add(
                Turn(
                    campaign_id=campaign_id,
                    role=RECAP_TURN_ROLE,
                    content=self._build_import_chat_summary(recap_text),
                    dice_result=None,
                    model_name=campaign.model_id,
                )
            )
            self.session.commit()

        updated = load_campaign(self.session, campaign_id)
        if updated is None:
            raise ValueError("Кампания была потеряна после импорта.")
        return serialize_campaign(updated)

    def _maybe_update_story_recap(self, campaign_id: int, *, force: bool = False, prompt_tokens: int = 0) -> str | None:
        if not self.settings.recap_enabled:
            return None

        campaign = load_campaign(self.session, campaign_id)
        if campaign is None:
            return None

        assistant_turns = [turn for turn in campaign.turns if turn.role == "assistant"]
        if not assistant_turns and not force:
            return None

        should_recap = force or (prompt_tokens >= int(self.settings.recap_trigger_context_tokens))
        if not should_recap:
            return None

        recap = campaign.recap
        legacy_recap_note = next((note for note in campaign.notes if note.title.strip() == LEGACY_RECAP_NOTE_TITLE), None)
        previous = recap.body if recap else (legacy_recap_note.body if legacy_recap_note else "")
        try:
            recap_text = self.llm_client.generate_story_recap(campaign, previous_recap=previous)
        except Exception:
            # Recap is a quality-of-life feature; never break gameplay on failure.
            return None

        if recap is None:
            recap = CampaignRecap(
                campaign_id=campaign_id,
                body=recap_text,
                source="model",
            )
            self.session.add(recap)
        else:
            recap.body = recap_text
            recap.source = "model"

        if legacy_recap_note is not None:
            self.session.delete(legacy_recap_note)

        campaign.updated_at = utcnow()
        self.session.commit()

        # If context is getting huge, shrink the chat log into a single recap turn.
        if assistant_turns and prompt_tokens >= int(self.settings.recap_trigger_context_tokens):
            self._replace_chat_with_recap(campaign_id, recap_text)
        return recap_text

    def _build_import_chat_summary(self, recap_text: str | None) -> str:
        if recap_text and recap_text.strip():
            return f"[РЕКАП]\nИмпорт завершён. Короткая сводка текущего положения:\n\n{recap_text.strip()}"
        return (
            "[РЕКАП]\n"
            "Импорт завершён. Память мира обновлена: проверь слева локации, персонажей, квесты и заметки. "
            "Если сводка не появилась подробно, можно сделать первый ход с просьбой: “кратко напомни, где я и что происходит”."
        )

    def _replace_chat_with_recap(self, campaign_id: int, recap_text: str) -> None:
        campaign = load_campaign(self.session, campaign_id)
        if campaign is None:
            return

        keep_last = max(int(self.settings.recap_keep_last_turns), 0)
        if keep_last > 0:
            keep = list(campaign.turns[-keep_last:])
        else:
            keep = []

        for turn in list(campaign.turns):
            if turn in keep:
                continue
            self.session.delete(turn)

        recap_turn = Turn(
            campaign_id=campaign_id,
            role=RECAP_TURN_ROLE,
            content=f"[РЕКАП]\n{recap_text}".strip(),
            dice_result=None,
            model_name=campaign.model_id,
        )
        self.session.add(recap_turn)
        campaign.updated_at = utcnow()
        self.session.commit()

    def _advance_timed_quests(self, campaign: object) -> None:
        quests = getattr(campaign, "quests", [])
        changed = False
        for quest in quests:
            if not isinstance(quest, Quest) or quest.status != "active":
                continue

            state = decode_quest_state(quest.progress_note)
            turns_remaining = state["turns_remaining"]
            turns_total = state["turns_total"]
            auto_decrement = bool(state["auto_decrement"])
            if not auto_decrement or not isinstance(turns_remaining, int):
                continue

            next_turns = max(turns_remaining - 1, 0)
            if next_turns == turns_remaining:
                continue

            body = str(state["body"] or "").strip()
            if next_turns == 0:
                quest.status = "failed"
                if "Срок истек" not in body and "время вышло" not in body.lower():
                    body = f"{body} Срок истек.".strip()

            quest.progress_note = encode_quest_state(
                body,
                kind=str(state["kind"] or "deadline"),
                turns_remaining=next_turns,
                turns_total=turns_total if isinstance(turns_total, int) else max(turns_remaining, 1),
                auto_decrement=auto_decrement and next_turns > 0 and quest.status == "active",
            )
            changed = True

        if changed:
            campaign.updated_at = utcnow()
            self.session.flush()
