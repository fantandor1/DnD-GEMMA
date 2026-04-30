from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from rpg_dm.config import Settings
from rpg_dm.db import Base
from rpg_dm.schemas import CampaignCreatePayload, CampaignUpdatePayload, HeroUpdatePayload
from rpg_dm.services.campaign_service import CampaignService


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    return SessionLocal()


def test_update_campaign_changes_model_goal_and_prompt(tmp_path: Path) -> None:
    session = make_session()
    settings = Settings(database_path=tmp_path / "campaign.sqlite3")
    service = CampaignService(
        session,
        settings,
        available_models=["google/gemma-4-e4b", "google/gemma-4-26b-a4b"],
    )
    created = service.create_campaign(
        CampaignCreatePayload(
            title="Coffee Run",
            setting_name="Corp Fantasy",
            goal="Get the signature",
            tone="grim office comedy",
            system_prompt="Old prompt",
            model_id="google/gemma-4-e4b",
            hero_name="Кобольд",
            hero_archetype="Инженер",
            hero_description="Ловкий офисный выживальщик",
            hero_inventory_text="Металлолом x3",
            brute_force=-1,
            bureaucracy=3,
            soft_skills=1,
            evasion=2,
            stress=0,
            max_stress=7,
            scrap=3,
        )
    )

    updated = service.update_campaign(
        created.id,
        CampaignUpdatePayload(
            goal="Добраться до HR-Лича и выбить подпись",
            system_prompt="New prompt",
            model_id="google/gemma-4-26b-a4b",
        ),
    )

    assert updated.goal == "Добраться до HR-Лича и выбить подпись"
    assert updated.system_prompt == "New prompt"
    assert updated.model_id == "google/gemma-4-26b-a4b"


def test_update_hero_changes_stats_inventory_and_current_location(tmp_path: Path) -> None:
    session = make_session()
    settings = Settings(database_path=tmp_path / "hero.sqlite3")
    service = CampaignService(session, settings, available_models=["googleapi/gemma-4-31b-it"])
    created = service.create_campaign(
        CampaignCreatePayload(
            title="Coffee Run",
            setting_name="Corp Fantasy",
            goal="Get the signature",
            tone="grim office comedy",
            system_prompt="Old prompt",
            model_id="googleapi/gemma-4-31b-it",
            hero_name="Кобольд",
            hero_archetype="Инженер",
            hero_description="Ловкий офисный выживальщик",
            hero_inventory_text="Металлолом x3",
            brute_force=-1,
            bureaucracy=3,
            soft_skills=1,
            evasion=2,
            stress=0,
            max_stress=7,
            scrap=3,
        )
    )

    updated = service.update_hero(
        created.id,
        HeroUpdatePayload(
            name="Кобольд-ремонтник",
            archetype="Инженер отдела кофе",
            description="Стал увереннее и злее.",
            status_text="В строю",
            current_location_name="Вход в Бюрократическую Цитадель",
            inventory_text="Заявление на кофемашину x1\nМеталлолом x2",
            brute_force=-1,
            bureaucracy=4,
            soft_skills=1,
            evasion=2,
            stress=1,
            max_stress=7,
            scrap=2,
        ),
    )

    assert updated.hero.name == "Кобольд-ремонтник"
    assert updated.hero.stats["bureaucracy"] == 4
    assert updated.hero.stats["scrap"] == 2
    assert updated.hero.current_location is not None
    assert updated.hero.current_location.name == "Вход в Бюрократическую Цитадель"
    assert updated.hero.inventory[0]["name"] == "Заявление на кофемашину"
