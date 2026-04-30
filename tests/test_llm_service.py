from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from rpg_dm.config import Settings
from rpg_dm.db import Base
from rpg_dm.models import Campaign, Hero
from rpg_dm.schemas import WorldDelta
from rpg_dm.services.llm_service import LMStudioClient, LMStudioError


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    return SessionLocal()


class FallbackClient(LMStudioClient):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.response_formats: list[dict | None] = []

    def _chat_completion(self, **kwargs):  # type: ignore[override]
        response_format = kwargs.get("response_format")
        self.response_formats.append(response_format)
        if response_format is not None:
            raise LMStudioError("Model does not support structured output")
        return (
            """
            {
              "current_location_name": "Вестибюль бюрократии",
              "hero": {
                "status_text": "Кобольд переводит дух."
              },
              "notes": [
                {
                  "title": "Новая зона",
                  "body": "Герой впервые вошел в вестибюль.",
                  "category": "canon",
                  "importance": "medium",
                  "is_pinned": true
                }
              ]
            }
            """,
            "stop",
        )


class GeminiRoutingClient(LMStudioClient):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.called_provider: str | None = None

    def _list_lm_studio_models(self) -> list[str]:
        return ["google/gemma-4-e4b"]

    def _list_gemini_models(self) -> list[str]:
        return ["googleapi/gemma-4-31b-it", "googleapi/gemini-2.5-flash-lite"]

    def _chat_completion_gemini(self, **kwargs):  # type: ignore[override]
        self.called_provider = "gemini"
        return ("Готово.", "stop")


def test_extract_world_delta_falls_back_when_schema_mode_is_rejected(tmp_path: Path) -> None:
    session = make_session()
    settings = Settings(database_path=tmp_path / "fallback.sqlite3")
    campaign = Campaign(
        title="Test",
        setting_name="Fantasy Corp",
        goal="Find approval",
        tone="Dry humor",
        system_prompt="Prompt",
        model_id="google/gemma-4-e4b",
    )
    campaign.hero = Hero(
        name="Кобольд",
        archetype="Инженер",
        description="Мастерит на коленке",
        stats={"stress": 0, "max_stress": 7, "scrap": 3},
        inventory=[{"name": "Металлолом", "quantity": 3, "description": "", "tags": []}],
        status_text="Старт",
    )
    session.add(campaign)
    session.commit()

    client = FallbackClient(settings)
    delta, raw_payload = client.extract_world_delta(
        campaign,
        player_message="Я захожу в холл и озираюсь.",
        dice_result=None,
        assistant_message="Ты входишь в вестибюль бюрократии и чувствуешь запах пережженного кофе.",
    )

    assert delta.current_location_name == "Вестибюль бюрократии"
    assert delta.hero.status_text == "Кобольд переводит дух."
    assert "Новая зона" in raw_payload
    assert client.response_formats[0] is not None
    assert client.response_formats[1] is None


def test_list_models_combines_lm_studio_and_gemini_models(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path / "models.sqlite3", gemini_api_key="test-key")
    client = GeminiRoutingClient(settings)

    models = client.list_models()

    assert models == [
        "google/gemma-4-e4b",
        "googleapi/gemma-4-31b-it",
        "googleapi/gemini-2.5-flash-lite",
    ]


def test_generate_narrative_routes_to_gemini_for_gemini_models(tmp_path: Path) -> None:
    session = make_session()
    settings = Settings(database_path=tmp_path / "gemini.sqlite3", gemini_api_key="test-key")
    campaign = Campaign(
        title="Test",
        setting_name="Fantasy Corp",
        goal="Find approval",
        tone="Dry humor",
        system_prompt="Prompt",
        model_id="googleapi/gemma-4-31b-it",
    )
    campaign.hero = Hero(
        name="Кобольд",
        archetype="Инженер",
        description="Мастерит на коленке",
        stats={"stress": 0, "max_stress": 7, "scrap": 3},
        inventory=[{"name": "Металлолом", "quantity": 3, "description": "", "tags": []}],
        status_text="Старт",
    )
    session.add(campaign)
    session.commit()

    client = GeminiRoutingClient(settings)
    response = client.generate_narrative(campaign, "Начни сцену.", None)

    assert response == "Готово."
    assert client.called_provider == "gemini"


def test_normalize_schema_preserves_real_title_properties() -> None:
    schema = WorldDelta.model_json_schema()

    normalized = LMStudioClient._normalize_schema(schema)

    assert "title" not in normalized
    assert "title" in normalized["$defs"]["NoteDelta"]["properties"]
    assert "title" in normalized["$defs"]["QuestDelta"]["properties"]
    assert normalized["$defs"]["NoteDelta"]["properties"]["title"]["type"] == "string"
    assert normalized["$defs"]["QuestDelta"]["properties"]["title"]["type"] == "string"


def test_hud_fallback_recovers_location_stats_and_inventory() -> None:
    delta = WorldDelta()

    enriched = LMStudioClient._apply_narrative_hud_fallback(
        delta,
        """
        ***
        **HUD**
        **Локация:** Вход в Бюрократическую Цитадель
        **Стресс:** 0/7
        **Металлолом:** 3
        **Инвентарь:** Заявление на кофемашину (нужна подпись), Металлолом x3
        """,
    )

    assert enriched.hero.current_location_name == "Вход в Бюрократическую Цитадель"
    assert enriched.hero.stats == {"stress": 0, "max_stress": 7, "scrap": 3}
    assert [item.name for item in enriched.hero.inventory] == ["Заявление на кофемашину", "Металлолом"]
    assert enriched.hero.inventory[0].description == "нужна подпись"
    assert enriched.hero.inventory[1].quantity == 3
    assert "current_location_name" in enriched.hero.model_fields_set
    assert "stats" in enriched.hero.model_fields_set
    assert "inventory" in enriched.hero.model_fields_set


class InlineDeltaClient(LMStudioClient):
    def _chat_completion(self, **kwargs):  # type: ignore[override]
        raise LMStudioError("offline")


def test_extract_world_delta_can_fall_back_to_dm_system_block(tmp_path: Path) -> None:
    session = make_session()
    settings = Settings(database_path=tmp_path / "inline.sqlite3")
    campaign = Campaign(
        title="Test",
        setting_name="Fantasy Corp",
        goal="Find approval",
        tone="Dry humor",
        system_prompt="Prompt",
        model_id="google/gemma-4-e4b",
    )
    campaign.hero = Hero(
        name="Кобольд",
        archetype="Инженер",
        description="Мастерит на коленке",
        stats={"stress": 0, "max_stress": 7, "scrap": 3},
        inventory=[{"name": "Металлолом", "quantity": 3, "description": "", "tags": []}],
        status_text="Старт",
    )
    session.add(campaign)
    session.commit()

    client = InlineDeltaClient(settings)
    delta, raw_payload = client.extract_world_delta(
        campaign,
        player_message="Я вхожу внутрь.",
        dice_result=None,
        assistant_message="""
        Сцена началась.
        [DM_SYSTEM]
        {
          "current_location_name": "Вход в Бюрократическую Цитадель",
          "locations": [
            {
              "name": "Вход в Бюрократическую Цитадель",
              "summary": "Пропускной зал с турникетами.",
              "atmosphere": "Большой холодный холл с запахом старого кофе.",
              "danger_level": "medium",
              "group_path": "Бюрократическая Цитадель / Вход",
              "notable_features": ["турникеты"],
              "exits": ["центральный холл"],
              "tags": ["checkpoint"]
            }
          ]
        }
        [/DM_SYSTEM]
        """,
    )

    assert delta.current_location_name == "Вход в Бюрократическую Цитадель"
    assert delta.locations[0].summary == "Пропускной зал с турникетами."
    assert delta.locations[0].group_path == "Бюрократическая Цитадель / Вход"
    assert '"current_location_name": "Вход в Бюрократическую Цитадель"' in raw_payload


def test_sanitize_narrative_removes_dm_system_block() -> None:
    content = """
    Текст сцены.
    [DM_SYSTEM]
    {"notes": [{"title": "X", "body": "Y"}]}
    [/DM_SYSTEM]
    """

    cleaned = LMStudioClient.sanitize_narrative(content)

    assert "Текст сцены." in cleaned
    assert "DM_SYSTEM" not in cleaned
