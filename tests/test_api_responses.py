from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from rpg_dm.db import Base
from rpg_dm.main import app
from rpg_dm.models import Campaign, Hero, MemoryUpdate, Turn
from rpg_dm.services.serialization import serialize_campaign


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    return SessionLocal()


def test_serialize_campaign_returns_json_safe_datetimes() -> None:
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
        name="Кобольд",
        archetype="Инженер",
        description="Тестовый герой",
        stats={"stress": 1, "max_stress": 7, "scrap": 3},
        inventory=[{"name": "Металлолом", "quantity": 3, "description": "", "tags": []}],
        status_text="Старт",
    )
    session.add(campaign)
    session.commit()
    session.add(Turn(campaign_id=campaign.id, role="assistant", content="Scene", model_name="google/gemma-4-e4b"))
    session.add(MemoryUpdate(campaign_id=campaign.id, status="applied"))
    session.commit()
    session.refresh(campaign)

    snapshot = serialize_campaign(campaign)

    json.dumps(snapshot)
    assert isinstance(snapshot["turns"][0]["created_at"], str)
    assert isinstance(snapshot["memory_updates"][0]["created_at"], str)


def test_api_returns_json_detail_for_unhandled_errors(monkeypatch) -> None:
    def explode(self, campaign_id, payload):  # type: ignore[no-untyped-def]
        raise TypeError("datetime is not JSON serializable")

    monkeypatch.setattr("rpg_dm.main.GameService.process_turn", explode)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/campaigns/1/messages", json={"message": "test"})

    assert response.status_code == 500
    assert response.json()["detail"] == "TypeError: datetime is not JSON serializable"


def test_play_view_renders_scene_shell(monkeypatch) -> None:
    monkeypatch.setattr("rpg_dm.main.LMStudioClient.list_models", lambda self: [])

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/?view=play")

    assert response.status_code == 200
    assert 'data-view-mode="play"' in response.text
