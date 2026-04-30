from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import Settings
from ..models import Campaign, Character, Hero, Location, Note, Quest, Turn
from ..prompts import render_inventory_inline_text, render_inventory_text, render_stats_text
from ..utils import compact_text, decode_quest_state, extract_group_path


CAMPAIGN_LOAD_OPTIONS = (
    selectinload(Campaign.hero).selectinload(Hero.current_location),
    selectinload(Campaign.locations),
    selectinload(Campaign.characters).selectinload(Character.location),
    selectinload(Campaign.quests),
    selectinload(Campaign.notes),
    selectinload(Campaign.recap),
    selectinload(Campaign.memory_updates),
    selectinload(Campaign.turns),
)


def load_campaign(session: Session, campaign_id: int) -> Campaign | None:
    stmt = select(Campaign).options(*CAMPAIGN_LOAD_OPTIONS).where(Campaign.id == campaign_id)
    return session.scalar(stmt)


def load_campaigns(session: Session) -> list[Campaign]:
    stmt = select(Campaign).options(*CAMPAIGN_LOAD_OPTIONS).order_by(Campaign.updated_at.desc())
    return list(session.scalars(stmt).all())


def build_memory_block(campaign: Campaign, settings: Settings) -> str:
    hero = campaign.hero
    current_location = hero.current_location.name if hero and hero.current_location else "Неизвестна"
    hero_block = (
        f"[ГЕРОЙ]\n"
        f"Имя: {hero.name}\n"
        f"Архетип: {hero.archetype}\n"
        f"Описание: {compact_text(hero.description, 180)}\n"
        f"Статы: {hero.stats}\n"
        f"Локация: {current_location}\n"
        f"Статус: {compact_text(hero.status_text or 'Без особых состояний', 140)}\n"
        f"Инвентарь:\n{render_inventory_text(hero.inventory)}"
    )

    locations = sorted(campaign.locations, key=lambda item: _sortable_dt(item.updated_at), reverse=True)
    location_lines = []
    for location in locations[: settings.prompt_location_limit]:
        features = ", ".join(location.notable_features or []) or "нет"
        exits = ", ".join(location.exits or []) or "неизвестны"
        group_path = extract_group_path(location.tags) or "без группы"
        detailed = compact_text(location.atmosphere or location.summary, 220)
        location_lines.append(
            f"- {location.name}: {compact_text(location.summary, 120)} "
            f"(группа: {group_path}, подробности: {detailed}, "
            f"опасность: {location.danger_level}, приметы: {features}, выходы: {exits})"
        )
    location_block = "[ЛОКАЦИИ]\n" + ("\n".join(location_lines) if location_lines else "Пока не открыты.")

    characters = sorted(campaign.characters, key=lambda item: _sortable_dt(item.updated_at), reverse=True)
    character_lines = []
    for character in characters[: settings.prompt_character_limit]:
        loc_name = character.location.name if character.location else "неизвестно"
        stats_text = compact_text(render_stats_text(character.stats or {}), 120)
        inventory_text = compact_text(render_inventory_inline_text(character.inventory or []), 120)
        character_lines.append(
            f"- {character.name} ({character.role}, {loc_name}): "
            f"{compact_text(character.summary or 'Без подробностей', 100)} "
            f"[характер: {compact_text(character.personality or 'не раскрыт', 60)}, статус: {character.status or 'active'}, "
            f"отношение: {character.attitude or 'neutral'}, жив: {'да' if character.is_alive else 'нет'}, "
            f"статы: {compact_text(stats_text, 80)}, инвентарь: {compact_text(inventory_text, 80)}]"
        )
    character_block = "[ПЕРСОНАЖИ]\n" + ("\n".join(character_lines) if character_lines else "Пока никого нет.")

    quests = sorted(campaign.quests, key=lambda item: _sortable_dt(item.updated_at), reverse=True)
    quest_lines = []
    for quest in quests[:5]:
        quest_state = decode_quest_state(quest.progress_note)
        timer_text = ""
        if isinstance(quest_state["turns_remaining"], int) and isinstance(quest_state["turns_total"], int):
            timer_text = f" [таймер: {quest_state['turns_remaining']}/{quest_state['turns_total']}]"
        quest_lines.append(f"- {quest.title}: {quest.status}{timer_text}. {compact_text(quest.description, 90)}")
    quest_block = "[КВЕСТЫ]\n" + ("\n".join(quest_lines) if quest_lines else f"- Главная цель: {campaign.goal}")

    recap_body = compact_text(campaign.recap.body, 1200) if campaign.recap and campaign.recap.body else ""
    recap_block = "[РЕКАП_КАМПАНИИ]\n" + (recap_body if recap_body else "Пока нет отдельного рекапа.")

    pinned_notes = [note for note in campaign.notes if note.is_pinned]
    notes = sorted(pinned_notes or campaign.notes, key=lambda item: _sortable_dt(item.updated_at), reverse=True)
    note_lines = []
    for note in notes[: settings.prompt_note_limit]:
        note_lines.append(f"- {note.title} [{note.category}/{note.importance}]: {compact_text(note.body, 100)}")
    note_block = "[ЗАМЕТКИ]\n" + ("\n".join(note_lines) if note_lines else "Нет заметок.")

    return "\n\n".join([hero_block, location_block, character_block, quest_block, recap_block, note_block])


def recent_turn_messages(campaign: Campaign, window: int) -> list[dict[str, str]]:
    turns = campaign.turns[-window:]
    messages: list[dict[str, str]] = []
    for turn in turns:
        if turn.role not in {"user", "assistant"}:
            continue
        content = turn.content
        if turn.role == "user" and turn.dice_result is not None:
            content = f"{content}\n\n[Игрок бросил куб и получил: {turn.dice_result}]"
        if turn.role == "assistant":
            content = compact_text(content, 900)
        else:
            content = compact_text(content, 500)
        messages.append({"role": turn.role, "content": content})
    return messages


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _sortable_dt(value: datetime | None) -> float:
    normalized = _normalize_datetime(value)
    if normalized is None:
        return 0.0
    return normalized.timestamp()


def _serialize_datetime(value: datetime | None) -> str | None:
    normalized = _normalize_datetime(value)
    if normalized is None:
        return None
    return normalized.isoformat()


def _serialize_locations(campaign: Campaign) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    serialized_locations: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for location in campaign.locations:
        group_path = extract_group_path(location.tags)
        serialized_location = {
            "id": location.id,
            "name": location.name,
            "summary": location.summary,
            "details": location.atmosphere,
            "danger_level": location.danger_level,
            "group_path": group_path,
            "notable_features": location.notable_features,
            "exits": location.exits,
            "tags": location.tags,
        }
        serialized_locations.append(serialized_location)
        grouped.setdefault(group_path or "Прочее", []).append(serialized_location)

    location_groups = [
        {"name": group_name, "locations": group_locations}
        for group_name, group_locations in sorted(grouped.items(), key=lambda item: item[0].lower())
    ]
    return serialized_locations, location_groups


def _serialize_quests(campaign: Campaign) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for quest in campaign.quests:
        state = decode_quest_state(quest.progress_note)
        serialized.append(
            {
                "id": quest.id,
                "title": quest.title,
                "description": quest.description,
                "status": quest.status,
                "progress_note": state["body"],
                "kind": state["kind"] or ("main" if quest.title.strip().lower() == "главная цель" else "side"),
                "turns_remaining": state["turns_remaining"],
                "turns_total": state["turns_total"],
                "auto_decrement": state["auto_decrement"],
            }
        )
    return serialized


def _serialize_turn(turn: Turn) -> dict[str, Any]:
    return {
        "id": turn.id,
        "role": turn.role,
        "content": turn.content,
        "dice_result": turn.dice_result,
        "created_at": _serialize_datetime(turn.created_at),
        "model_name": turn.model_name,
    }


def serialize_campaign(campaign: Campaign) -> dict[str, Any]:
    hero = campaign.hero
    serialized_locations, location_groups = _serialize_locations(campaign)
    serialized_quests = _serialize_quests(campaign)
    current_location_name = hero.current_location.name if hero.current_location else None
    current_location_details = next(
        (location for location in serialized_locations if location["name"] == current_location_name),
        None,
    )
    latest_assistant_turn = next((turn for turn in reversed(campaign.turns) if turn.role == "assistant"), None)
    latest_user_turn = next((turn for turn in reversed(campaign.turns) if turn.role == "user"), None)
    return {
        "id": campaign.id,
        "title": campaign.title,
        "setting_name": campaign.setting_name,
        "goal": campaign.goal,
        "tone": campaign.tone,
        "system_prompt": campaign.system_prompt,
        "model_id": campaign.model_id,
        "hero": {
            "name": hero.name,
            "archetype": hero.archetype,
            "description": hero.description,
            "status_text": hero.status_text,
            "stats": hero.stats,
            "inventory": hero.inventory,
            "current_location": current_location_name,
        },
        "turns": [_serialize_turn(turn) for turn in campaign.turns],
        "latest_assistant_turn": _serialize_turn(latest_assistant_turn) if latest_assistant_turn else None,
        "latest_user_turn": _serialize_turn(latest_user_turn) if latest_user_turn else None,
        "locations": serialized_locations,
        "location_groups": location_groups,
        "current_location_details": current_location_details,
        "characters": [
            {
                "id": character.id,
                "name": character.name,
                "role": character.role,
                "summary": character.summary,
                "personality": character.personality,
                "status": character.status,
                "attitude": character.attitude,
                "is_alive": character.is_alive,
                "stats": character.stats,
                "inventory": character.inventory,
                "location": character.location.name if character.location else None,
            }
            for character in campaign.characters
        ],
        "quests": serialized_quests,
        "recap": {
            "body": campaign.recap.body if campaign.recap else "",
            "updated_at": _serialize_datetime(campaign.recap.updated_at) if campaign.recap else None,
        },
        "notes": [
            {
                "id": note.id,
                "title": note.title,
                "body": note.body,
                "category": note.category,
                "importance": note.importance,
                "is_pinned": note.is_pinned,
                "source": note.source,
            }
            for note in campaign.notes
        ],
        "memory_updates": [
            {
                "id": item.id,
                "status": item.status,
                "error_message": item.error_message,
                "created_at": _serialize_datetime(item.created_at),
            }
            for item in campaign.memory_updates[:10]
        ],
    }
