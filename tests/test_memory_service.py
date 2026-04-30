from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from rpg_dm.config import Settings
from rpg_dm.db import Base
from rpg_dm.models import Campaign, Character, Hero, Location, Note, Quest
from rpg_dm.schemas import CharacterDelta, HeroDelta, LocationDelta, NoteDelta, QuestDelta, WorldDelta
from rpg_dm.services.memory_service import apply_world_delta
from rpg_dm.services.serialization import build_memory_block, serialize_campaign
from rpg_dm.utils import decode_quest_state, encode_quest_state


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    return SessionLocal()


def test_apply_world_delta_creates_location_and_updates_hero() -> None:
    session = make_session()
    campaign = Campaign(
        title="Test",
        setting_name="Fantasy Corp",
        goal="Find coffee approval",
        tone="Dry humor",
        system_prompt="Test prompt",
        model_id="google/gemma-4-e4b",
    )
    campaign.hero = Hero(
        name="Кобольд",
        archetype="Инженер",
        description="Тестовый герой",
        stats={"stress": 0, "max_stress": 7, "scrap": 3},
        inventory=[{"name": "Металлолом", "quantity": 3, "description": "", "tags": []}],
        status_text="Старт",
    )
    session.add(campaign)
    session.commit()

    delta = WorldDelta(
        current_location_name="Бюрократическая Цитадель",
        hero=HeroDelta(
            status_text="Нервы на пределе.",
            stats={"stress": 2, "scrap": 2},
            inventory=[{"name": "Металлолом", "quantity": 2, "description": "", "tags": []}],
        ),
        locations=[
            LocationDelta(
                name="Бюрократическая Цитадель",
                summary="Гулкий мраморный холл с бесконечной очередью.",
                atmosphere="Сухой воздух, звон турникетов и запах дешевого кофе.",
                danger_level="medium",
                notable_features=["турникеты", "регистратура"],
                exits=["лифты", "служебный коридор"],
                tags=["office", "hub"],
            )
        ],
        notes=[
            NoteDelta(
                title="Первое впечатление",
                body="На входе контроль серьезнее, чем в подземелье дракона.",
                category="canon",
                importance="medium",
                is_pinned=True,
            )
        ],
    )

    apply_world_delta(session, campaign, delta, assistant_turn_id=1)
    session.commit()
    session.refresh(campaign.hero)

    assert campaign.hero.current_location is not None
    assert campaign.hero.current_location.name == "Бюрократическая Цитадель"
    assert campaign.hero.stats["stress"] == 2
    assert campaign.hero.stats["scrap"] == 2
    assert campaign.hero.inventory[0]["quantity"] == 2
    assert session.query(Note).count() == 1


def test_build_memory_block_mentions_goal_inventory_and_location(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path / "test.sqlite3")
    session = make_session()
    campaign = Campaign(
        title="Coffee Quest",
        setting_name="Corp Fantasy",
        goal="Recover the stamp",
        tone="grim comedy",
        system_prompt="Prompt",
        model_id="google/gemma-4-e4b",
    )
    campaign.hero = Hero(
        name="Медный Кобольд",
        archetype="Инженер",
        description="Слишком маленький для честного боя.",
        stats={"stress": 1, "max_stress": 7, "scrap": 3},
        inventory=[{"name": "Металлолом", "quantity": 3, "description": "", "tags": []}],
        status_text="Прячется за стойкой.",
    )
    session.add(campaign)
    session.commit()

    block = build_memory_block(campaign, settings)

    assert "Медный Кобольд" in block
    assert "Металлолом x3" in block
    assert "Recover the stamp" in block
    assert "[ЛОКАЦИИ]" in block


def test_apply_world_delta_preserves_character_stats_and_inventory_when_partial_update_omits_them() -> None:
    session = make_session()
    campaign = Campaign(
        title="Test",
        setting_name="Fantasy Corp",
        goal="Find coffee approval",
        tone="Dry humor",
        system_prompt="Test prompt",
        model_id="google/gemma-4-e4b",
    )
    campaign.hero = Hero(
        name="Кобольд",
        archetype="Инженер",
        description="Тестовый герой",
        stats={"stress": 0, "max_stress": 7, "scrap": 3},
        inventory=[{"name": "Металлолом", "quantity": 3, "description": "", "tags": []}],
        status_text="Старт",
    )
    campaign.characters.append(
        Character(
            slug="секретарь-цербер",
            name="Секретарь-цербер",
            role="enemy",
            summary="Много лает и любит печати.",
            personality="Подозрительный",
            status="alert",
            attitude="hostile",
            is_alive=True,
            stats={"hp": 12, "armor": 2},
            inventory=[{"name": "Связка пропусков", "quantity": 1, "description": "", "tags": []}],
        )
    )
    session.add(campaign)
    session.commit()

    delta = WorldDelta(
        characters=[
            CharacterDelta(
                name="Секретарь-цербер",
                summary="Теперь он отвлекся на спор с курьером.",
            )
        ]
    )

    apply_world_delta(session, campaign, delta, assistant_turn_id=2)
    session.commit()

    character = session.query(Character).one()
    assert character.summary == "Теперь он отвлекся на спор с курьером."
    assert character.stats == {"hp": 12, "armor": 2}
    assert character.inventory == [{"name": "Связка пропусков", "quantity": 1, "description": "", "tags": []}]


def test_build_memory_block_mentions_character_stats_and_inventory(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path / "characters.sqlite3")
    session = make_session()
    campaign = Campaign(
        title="Coffee Quest",
        setting_name="Corp Fantasy",
        goal="Recover the stamp",
        tone="grim comedy",
        system_prompt="Prompt",
        model_id="google/gemma-4-e4b",
    )
    campaign.hero = Hero(
        name="Медный Кобольд",
        archetype="Инженер",
        description="Слишком маленький для честного боя.",
        stats={"stress": 1, "max_stress": 7, "scrap": 3},
        inventory=[{"name": "Металлолом", "quantity": 3, "description": "", "tags": []}],
        status_text="Прячется за стойкой.",
    )
    campaign.characters.append(
        Character(
            slug="гоблин-аудитор",
            name="Гоблин-аудитор",
            role="enemy",
            summary="Мелкий, злой и считает чужие печеньки.",
            personality="Дотошный",
            status="active",
            attitude="hostile",
            is_alive=True,
            stats={"hp": 8, "check_bonus": 4},
            inventory=[{"name": "Счеты", "quantity": 1, "description": "", "tags": []}],
        )
    )
    session.add(campaign)
    session.commit()

    block = build_memory_block(campaign, settings)

    assert "Гоблин-аудитор" in block
    assert "hp: 8" in block
    assert "Счеты x1" in block


def test_apply_world_delta_groups_locations_and_keeps_detailed_description() -> None:
    session = make_session()
    campaign = Campaign(
        title="Tower Run",
        setting_name="Corp Fantasy",
        goal="Reach the summit",
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
    session.add(campaign)
    session.commit()

    apply_world_delta(
        session,
        campaign,
        WorldDelta(
            locations=[
                LocationDelta(
                    name="Зал турникетов",
                    summary="Узкий пропускной зал.",
                    atmosphere="Подробное описание зала с камнем, металлом и запахом кофе.",
                    danger_level="medium",
                    group_path="Башня Митинга / Этаж 1",
                    notable_features=["турникеты"],
                    exits=["лифт"],
                    tags=["checkpoint"],
                )
            ]
        ),
        assistant_turn_id=1,
    )
    session.commit()
    session.refresh(campaign)

    snapshot = serialize_campaign(campaign)

    assert snapshot["locations"][0]["details"] == "Подробное описание зала с камнем, металлом и запахом кофе."
    assert snapshot["locations"][0]["group_path"] == "Башня Митинга / Этаж 1"
    assert snapshot["location_groups"][0]["name"] == "Башня Митинга / Этаж 1"


def test_apply_world_delta_deduplicates_main_quest_when_copy_matches_goal() -> None:
    session = make_session()
    campaign = Campaign(
        title="Coffee Run",
        setting_name="Corp Fantasy",
        goal="Получить подпись HR-Лича на заявлении о кофемашине.",
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
            slug="main-goal",
            title="Главная цель",
            description=campaign.goal,
            status="active",
            progress_note=encode_quest_state("Идти вниз по башне.", kind="main"),
        )
    )
    session.add(campaign)
    session.commit()

    apply_world_delta(
        session,
        campaign,
        WorldDelta(
            quests=[
                QuestDelta(
                    title="Подпись для кофемашины",
                    description=campaign.goal,
                    kind="side",
                    status="active",
                    progress_note="Дубликат, который не должен создать новый квест.",
                )
            ]
        ),
    )
    session.commit()

    assert session.query(Quest).count() == 1
    quest = session.query(Quest).one()
    state = decode_quest_state(quest.progress_note)
    assert quest.title == "Главная цель"
    assert state["kind"] == "main"


def test_serialize_campaign_handles_mixed_naive_and_aware_datetimes(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path / "mixed-datetimes.sqlite3")
    campaign = Campaign(
        title="Mixed Time",
        setting_name="Corp Fantasy",
        goal="Stay alive",
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
    campaign.locations = [
        Location(
            slug="checkpoint",
            name="Пропускной пункт",
            summary="Короткое описание.",
            atmosphere="Подробное описание для памяти.",
            danger_level="medium",
            tags=["group:Башня / Этаж 1"],
            updated_at=datetime(2026, 4, 18, 10, 0, 0),
        ),
        Location(
            slug="archives",
            name="Архивный лифт",
            summary="Еще одно описание.",
            atmosphere="Еще одна подробная сцена.",
            danger_level="high",
            tags=["group:Башня / Этаж -1"],
            updated_at=datetime(2026, 4, 18, 11, 0, 0, tzinfo=timezone.utc),
        ),
    ]
    campaign.characters = [
        Character(
            slug="clerk",
            name="Клерк",
            summary="Смотрит косо.",
            updated_at=datetime(2026, 4, 18, 9, 0, 0),
        )
    ]
    campaign.quests = [
        Quest(
            slug="timer",
            title="Потолок не ждет",
            description="Надо спешить.",
            progress_note=encode_quest_state("Пыль сыплется.", turns_remaining=9, turns_total=10, auto_decrement=True),
            updated_at=datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc),
        )
    ]
    campaign.notes = [
        Note(
            title="Факт",
            body="Полезная заметка.",
            updated_at=datetime(2026, 4, 18, 8, 30, 0),
        )
    ]

    snapshot = serialize_campaign(campaign)
    memory_block = build_memory_block(campaign, settings)

    assert snapshot["locations"][0]["name"] in {"Пропускной пункт", "Архивный лифт"}
    assert "Потолок не ждет" in memory_block
