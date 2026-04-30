from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from rpg_dm.config import Settings
from rpg_dm.db import Base
from rpg_dm.models import Campaign, Hero, Quest
from rpg_dm.schemas import MessageRequest, WorldDelta
from rpg_dm.services.game_service import GameService
from rpg_dm.services.llm_service import LMStudioClient
from rpg_dm.services.serialization import load_campaign
from rpg_dm.utils import decode_quest_state, encode_quest_state


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    return SessionLocal()


class TimedQuestClient(LMStudioClient):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.seen_turns_remaining: int | None = None

    def generate_narrative(self, campaign: Campaign, player_message: str, dice_result: int | None) -> str:  # type: ignore[override]
        quest = next(item for item in campaign.quests if item.title == "Потолок не ждет")
        state = decode_quest_state(quest.progress_note)
        self.seen_turns_remaining = state["turns_remaining"]
        return "С потолка снова сыплется пыль.\n[DM_SYSTEM]\n{}\n[/DM_SYSTEM]"

    def extract_world_delta(  # type: ignore[override]
        self,
        campaign: Campaign,
        player_message: str,
        dice_result: int | None,
        assistant_message: str,
    ) -> tuple[WorldDelta, str]:
        return WorldDelta(), "{}"


def test_process_turn_decrements_active_timed_quests_before_generation(tmp_path: Path) -> None:
    session = make_session()
    settings = Settings(database_path=tmp_path / "timers.sqlite3")
    campaign = Campaign(
        title="Coffee Run",
        setting_name="Corp Fantasy",
        goal="Get the signature",
        tone="grim office comedy",
        system_prompt="Prompt",
        model_id="google/gemma-4-e4b",
    )
    campaign.hero = Hero(
        name="Кобольд",
        archetype="Инженер",
        description="Тестовый герой",
        stats={"stress": 0, "max_stress": 7, "scrap": 3},
        inventory=[],
        status_text="Старт",
    )
    campaign.quests.append(
        Quest(
            slug="ceiling",
            title="Потолок не ждет",
            description="Нужно решить проблему до обрушения потолка.",
            status="active",
            progress_note=encode_quest_state(
                "Пыль сыплется все сильнее.",
                kind="deadline",
                turns_remaining=10,
                turns_total=10,
                auto_decrement=True,
            ),
        )
    )
    session.add(campaign)
    session.commit()

    client = TimedQuestClient(settings)
    service = GameService(session, settings, client)

    snapshot = service.process_turn(
        campaign.id,
        MessageRequest(message="Я ищу несущую балку.", dice_result=None),
    )

    quest_snapshot = next(item for item in snapshot["quests"] if item["title"] == "Потолок не ждет")
    assert client.seen_turns_remaining == 9
    assert quest_snapshot["turns_remaining"] == 9
    assert quest_snapshot["turns_total"] == 10
    assert quest_snapshot["status"] == "active"

    reloaded = load_campaign(session, campaign.id)
    assert reloaded is not None
    quest = next(item for item in reloaded.quests if item.title == "Потолок не ждет")
    state = decode_quest_state(quest.progress_note)
    assert state["turns_remaining"] == 9
