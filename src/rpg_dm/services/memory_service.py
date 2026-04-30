from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Campaign, Character, Hero, Location, Note, Quest
from ..schemas import CharacterDelta, HeroDelta, LocationDelta, NoteDelta, QuestDelta, WorldDelta
from ..utils import decode_quest_state, encode_quest_state, extract_group_path, slugify, with_group_tag


def apply_world_delta(
    session: Session,
    campaign: Campaign,
    delta: WorldDelta,
    assistant_turn_id: int | None = None,
) -> None:
    hero = campaign.hero

    for location_delta in delta.locations:
        upsert_location(session, campaign.id, location_delta, assistant_turn_id)

    for character_delta in delta.characters:
        upsert_character(session, campaign.id, character_delta, assistant_turn_id)

    for quest_delta in delta.quests:
        upsert_quest(session, campaign, quest_delta)

    for note_delta in delta.notes:
        apply_note_delta(session, campaign.id, note_delta, assistant_turn_id)

    apply_hero_patch(session, campaign.id, hero, delta.hero)

    target_location_name = delta.hero.current_location_name or delta.current_location_name
    if target_location_name:
        hero.current_location = ensure_location(session, campaign.id, target_location_name, assistant_turn_id)


def ensure_location(
    session: Session,
    campaign_id: int,
    location_name: str,
    turn_id: int | None = None,
) -> Location:
    slug = slugify(location_name)
    stmt = select(Location).where(Location.campaign_id == campaign_id, Location.slug == slug)
    location = session.scalar(stmt)
    if location:
        location.last_seen_turn = turn_id
        return location

    location = Location(
        campaign_id=campaign_id,
        slug=slug,
        name=location_name.strip(),
        summary="",
        atmosphere="",
        danger_level="unknown",
        notable_features=[],
        exits=[],
        tags=[],
        first_seen_turn=turn_id,
        last_seen_turn=turn_id,
    )
    session.add(location)
    session.flush()
    return location


def upsert_location(
    session: Session,
    campaign_id: int,
    payload: LocationDelta,
    turn_id: int | None,
) -> Location:
    provided_fields = payload.model_fields_set
    slug = slugify(payload.name)
    stmt = select(Location).where(Location.campaign_id == campaign_id, Location.slug == slug)
    location = session.scalar(stmt)
    is_new = location is None
    if location is None:
        location = Location(
            campaign_id=campaign_id,
            slug=slug,
            name=payload.name.strip(),
            first_seen_turn=turn_id,
        )
        session.add(location)

    location.name = payload.name.strip()
    if is_new or "summary" in provided_fields:
        location.summary = payload.summary.strip()
    if is_new or "atmosphere" in provided_fields:
        location.atmosphere = payload.atmosphere.strip()
    if is_new or "danger_level" in provided_fields:
        location.danger_level = payload.danger_level.strip()
    if is_new or "notable_features" in provided_fields:
        location.notable_features = list(payload.notable_features)
    if is_new or "exits" in provided_fields:
        location.exits = list(payload.exits)
    if is_new or "tags" in provided_fields or "group_path" in provided_fields:
        next_group_path = payload.group_path
        if next_group_path is None and not is_new:
            next_group_path = extract_group_path(location.tags)
        location.tags = with_group_tag(list(payload.tags), next_group_path)
    location.last_seen_turn = turn_id
    session.flush()
    return location


def upsert_character(
    session: Session,
    campaign_id: int,
    payload: CharacterDelta,
    turn_id: int | None,
) -> Character:
    provided_fields = payload.model_fields_set
    slug = slugify(payload.name)
    stmt = select(Character).where(Character.campaign_id == campaign_id, Character.slug == slug)
    character = session.scalar(stmt)
    is_new = character is None
    if character is None:
        character = Character(
            campaign_id=campaign_id,
            slug=slug,
            name=payload.name.strip(),
            first_seen_turn=turn_id,
        )
        session.add(character)

    location = None
    if payload.location_name:
        location = ensure_location(session, campaign_id, payload.location_name, turn_id)

    character.name = payload.name.strip()
    if is_new or "role" in provided_fields:
        character.role = payload.role
    if is_new or "location_name" in provided_fields:
        character.location = location
    if is_new or "summary" in provided_fields:
        character.summary = payload.summary.strip()
    if is_new or "personality" in provided_fields:
        character.personality = payload.personality.strip()
    if is_new or "status" in provided_fields:
        character.status = payload.status.strip()
    if is_new or "attitude" in provided_fields:
        character.attitude = payload.attitude.strip()
    if is_new or "is_alive" in provided_fields:
        character.is_alive = payload.is_alive
    if is_new or "stats" in provided_fields:
        character.stats = dict(payload.stats)
    if is_new or "inventory" in provided_fields:
        character.inventory = [item.model_dump() for item in payload.inventory]
    character.last_seen_turn = turn_id
    session.flush()
    return character


def upsert_quest(session: Session, campaign: Campaign, payload: QuestDelta) -> Quest:
    provided_fields = payload.model_fields_set
    normalized_title = payload.title.strip()
    normalized_description = payload.description.strip()

    inferred_kind = payload.kind
    if normalized_title.lower() == "главная цель" or normalized_description == campaign.goal.strip():
        inferred_kind = "main"

    quest = None
    existing_main = next(
        (
            item
            for item in campaign.quests
            if item.title.strip().lower() == "главная цель"
            or decode_quest_state(item.progress_note)["kind"] == "main"
            or item.description.strip() == campaign.goal.strip()
        ),
        None,
    )

    if inferred_kind == "main":
        quest = existing_main
    else:
        if existing_main is not None and (
            normalized_title.lower() == existing_main.title.strip().lower()
            or normalized_description == existing_main.description.strip()
        ):
            quest = existing_main

    if quest is None:
        slug = slugify(normalized_title)
        stmt = select(Quest).where(Quest.campaign_id == campaign.id, Quest.slug == slug)
        quest = session.scalar(stmt)

    if quest is None and normalized_description:
        quest = next((item for item in campaign.quests if item.description.strip() == normalized_description), None)

    is_new = quest is None
    if quest is None:
        quest = Quest(
            campaign_id=campaign.id,
            slug=slugify(normalized_title),
            title=normalized_title,
        )
        session.add(quest)

    current_state = decode_quest_state(quest.progress_note)
    preserve_existing_main_title = (
        existing_main is not None
        and quest is existing_main
        and existing_main.title.strip().lower() == "главная цель"
        and normalized_title.lower() != "главная цель"
        and inferred_kind == "main"
    )
    if not preserve_existing_main_title:
        quest.title = normalized_title
        quest.slug = slugify(normalized_title)
    if is_new or "description" in provided_fields:
        quest.description = normalized_description
    if is_new or "status" in provided_fields:
        quest.status = payload.status

    note_body = str(current_state["body"] or "")
    if is_new or "progress_note" in provided_fields:
        note_body = payload.progress_note.strip()

    quest_kind = inferred_kind or current_state["kind"] or "side"
    turns_remaining = current_state["turns_remaining"]
    turns_total = current_state["turns_total"]
    auto_decrement = bool(current_state["auto_decrement"])

    if "turns_remaining" in provided_fields:
        turns_remaining = payload.turns_remaining
    if "turns_total" in provided_fields:
        turns_total = payload.turns_total
    if "auto_decrement" in provided_fields:
        auto_decrement = payload.auto_decrement

    quest.progress_note = encode_quest_state(
        note_body,
        kind=quest_kind if isinstance(quest_kind, str) else None,
        turns_remaining=turns_remaining if isinstance(turns_remaining, int) else None,
        turns_total=turns_total if isinstance(turns_total, int) else None,
        auto_decrement=auto_decrement,
    )
    session.flush()
    return quest


def apply_note_delta(session: Session, campaign_id: int, payload: NoteDelta, turn_id: int | None) -> Note | None:
    existing = (
        session.query(Note)
        .filter(Note.campaign_id == campaign_id)
        .filter(Note.title == payload.title.strip())
        .one_or_none()
    )

    if payload.action == "delete":
        if existing is not None:
            session.delete(existing)
            session.flush()
        return None

    if existing is None:
        note = Note(
            campaign_id=campaign_id,
            turn_id=turn_id,
            title=payload.title.strip(),
            body=payload.body.strip(),
            category=payload.category,
            importance=payload.importance,
            source="model",
            is_pinned=payload.is_pinned,
        )
        session.add(note)
    else:
        note = existing
        note.turn_id = turn_id
        note.body = payload.body.strip()
        note.category = payload.category
        note.importance = payload.importance
        note.source = "model"
        note.is_pinned = payload.is_pinned

    session.flush()
    return note


def create_note(session: Session, campaign_id: int, payload: NoteDelta, turn_id: int | None) -> Note:
    note = apply_note_delta(session, campaign_id, payload, turn_id)
    if note is None:
        note = Note(
            campaign_id=campaign_id,
            turn_id=turn_id,
            title=payload.title.strip(),
            body=payload.body.strip(),
            category=payload.category,
            importance=payload.importance,
            source="model",
            is_pinned=payload.is_pinned,
        )
        session.add(note)
        session.flush()
    return note


def apply_hero_patch(session: Session, campaign_id: int, hero: Hero, payload: HeroDelta) -> Hero:
    provided_fields = payload.model_fields_set
    if payload.name:
        hero.name = payload.name.strip()
    if payload.archetype:
        hero.archetype = payload.archetype.strip()
    if "description" in provided_fields:
        hero.description = (payload.description or "").strip()
    if "status_text" in provided_fields:
        hero.status_text = (payload.status_text or "").strip()
    if "stats" in provided_fields:
        merged = dict(hero.stats)
        merged.update(payload.stats)
        hero.stats = merged
    if "inventory" in provided_fields:
        hero.inventory = [item.model_dump() for item in payload.inventory]
    if payload.current_location_name:
        hero.current_location = ensure_location(session, campaign_id, payload.current_location_name)
    session.flush()
    return hero
