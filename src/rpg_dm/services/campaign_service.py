from __future__ import annotations

import re

from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Campaign, Hero, Location, Note, Quest
from ..prompts import (
    DEFAULT_GOAL,
    DEFAULT_HERO_ARCHETYPE,
    DEFAULT_HERO_DESCRIPTION,
    DEFAULT_HERO_INVENTORY,
    DEFAULT_HERO_NAME,
    DEFAULT_HERO_STATS,
    DEFAULT_SETTING_NAME,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TITLE,
    DEFAULT_TONE,
)
from ..schemas import CampaignCreatePayload, CampaignUpdatePayload, HeroUpdatePayload, NoteCreatePayload
from ..utils import encode_quest_state, slugify, utcnow
from .serialization import load_campaign, load_campaigns


class CampaignService:
    def __init__(self, session: Session, settings: Settings, available_models: list[str] | None = None) -> None:
        self.session = session
        self.settings = settings
        self.available_models = available_models or []

    def list_campaigns(self) -> list[Campaign]:
        return load_campaigns(self.session)

    def get_campaign(self, campaign_id: int) -> Campaign | None:
        return load_campaign(self.session, campaign_id)

    def get_or_seed_default_campaign(self) -> Campaign:
        campaigns = self.list_campaigns()
        if campaigns:
            return campaigns[0]

        payload = CampaignCreatePayload(
            title=DEFAULT_TITLE,
            setting_name=DEFAULT_SETTING_NAME,
            goal=DEFAULT_GOAL,
            tone=DEFAULT_TONE,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            model_id=self.pick_model(),
            hero_name=DEFAULT_HERO_NAME,
            hero_archetype=DEFAULT_HERO_ARCHETYPE,
            hero_description=DEFAULT_HERO_DESCRIPTION,
            hero_inventory_text=DEFAULT_HERO_INVENTORY,
            brute_force=DEFAULT_HERO_STATS["brute_force"],
            bureaucracy=DEFAULT_HERO_STATS["bureaucracy"],
            soft_skills=DEFAULT_HERO_STATS["soft_skills"],
            evasion=DEFAULT_HERO_STATS["evasion"],
            hp=DEFAULT_HERO_STATS.get("hp", 20),
            max_hp=DEFAULT_HERO_STATS.get("max_hp", 20),
            stress=DEFAULT_HERO_STATS["stress"],
            max_stress=DEFAULT_HERO_STATS["max_stress"],
            scrap=DEFAULT_HERO_STATS["scrap"],
        )
        return self.create_campaign(payload)

    def pick_model(self) -> str:
        if not self.available_models:
            return self.settings.default_model

        default_model = self.settings.default_model.lower()

        def sort_key(model_id: str) -> tuple[int, int, int, int, int, int, str]:
            normalized = model_id.lower()
            return (
                0 if normalized == default_model else 1,
                0 if "googleapi/gemma-4-31b-it" in normalized else 1,
                0 if "googleapi/" in normalized else 1,
                0 if "gemma" in normalized else 1,
                0 if any(token in normalized for token in ("e4b", "4b", "3b", "2b", "mini", "small")) else 1,
                0 if any(token in normalized for token in ("it", "instruct")) else 1,
                normalized,
            )

        return min(self.available_models, key=sort_key)

    def create_campaign(self, payload: CampaignCreatePayload) -> Campaign:
        inventory_items = self._parse_inventory_text(payload.hero_inventory_text)

        campaign = Campaign(
            title=payload.title.strip(),
            setting_name=payload.setting_name.strip(),
            goal=payload.goal.strip(),
            tone=payload.tone.strip(),
            system_prompt=payload.system_prompt.strip(),
            model_id=(payload.model_id or self.pick_model()).strip(),
        )
        hero = Hero(
            name=payload.hero_name.strip(),
            archetype=payload.hero_archetype.strip(),
            description=payload.hero_description.strip(),
            stats={
                "brute_force": payload.brute_force,
                "bureaucracy": payload.bureaucracy,
                "soft_skills": payload.soft_skills,
                "evasion": payload.evasion,
                "hp": payload.hp,
                "max_hp": payload.max_hp,
                "stress": payload.stress,
                "max_stress": payload.max_stress,
                "scrap": payload.scrap,
            },
            inventory=inventory_items,
            status_text="Игра только начинается.",
        )
        quest = Quest(
            slug=slugify("main-goal"),
            title="Главная цель",
            description=payload.goal.strip(),
            status="active",
            progress_note=encode_quest_state(
                "Квест создан при запуске кампании.",
                kind="main",
            ),
        )
        note = Note(
            title="Стартовая предпосылка",
            body="Герой должен выбить подпись на новую кофемашину для 23 этажа.",
            category="canon",
            importance="high",
            source="seed",
            is_pinned=True,
        )
        campaign.hero = hero
        campaign.quests.append(quest)
        campaign.notes.append(note)
        self.session.add(campaign)
        self.session.commit()
        return self.get_campaign(campaign.id) or campaign

    def add_note(self, campaign_id: int, payload: NoteCreatePayload) -> Campaign:
        campaign = self.get_campaign(campaign_id)
        if campaign is None:
            raise ValueError("Кампания не найдена.")

        note = Note(
            campaign_id=campaign_id,
            title=payload.title.strip(),
            body=payload.body.strip(),
            category=payload.category,
            importance=payload.importance,
            source="manual",
            is_pinned=payload.is_pinned,
        )
        self.session.add(note)
        campaign.updated_at = utcnow()
        self.session.commit()
        return self.get_campaign(campaign_id) or campaign

    def update_campaign(self, campaign_id: int, payload: CampaignUpdatePayload) -> Campaign:
        campaign = self.get_campaign(campaign_id)
        if campaign is None:
            raise ValueError("Кампания не найдена.")

        provided_fields = payload.model_fields_set
        if "title" in provided_fields and payload.title is not None:
            campaign.title = payload.title.strip()
        if "setting_name" in provided_fields and payload.setting_name is not None:
            campaign.setting_name = payload.setting_name.strip()
        if "goal" in provided_fields and payload.goal is not None:
            campaign.goal = payload.goal.strip()
            main_quest = next((item for item in campaign.quests if item.title.strip().lower() == "главная цель"), None)
            if main_quest is not None:
                main_quest.description = campaign.goal
        if "tone" in provided_fields:
            campaign.tone = (payload.tone or "").strip()
        if "system_prompt" in provided_fields and payload.system_prompt is not None:
            campaign.system_prompt = payload.system_prompt.strip()
        if "model_id" in provided_fields:
            campaign.model_id = (payload.model_id or "").strip() or self.pick_model()

        campaign.updated_at = utcnow()
        self.session.commit()
        return self.get_campaign(campaign_id) or campaign

    def delete_campaign(self, campaign_id: int) -> None:
        campaign = self.get_campaign(campaign_id)
        if campaign is None:
            raise ValueError("Кампания не найдена.")
        self.session.delete(campaign)
        self.session.commit()

    def delete_note(self, campaign_id: int, note_id: int) -> Campaign:
        campaign = self.get_campaign(campaign_id)
        if campaign is None:
            raise ValueError("Кампания не найдена.")

        note = next((item for item in campaign.notes if item.id == note_id), None)
        if note is None:
            raise ValueError("Заметка не найдена.")

        self.session.delete(note)
        campaign.updated_at = utcnow()
        self.session.commit()
        return self.get_campaign(campaign_id) or campaign

    def update_hero(self, campaign_id: int, payload: HeroUpdatePayload) -> Campaign:
        campaign = self.get_campaign(campaign_id)
        if campaign is None or campaign.hero is None:
            raise ValueError("Кампания или герой не найдены.")

        hero = campaign.hero
        hero.name = payload.name.strip()
        hero.archetype = payload.archetype.strip()
        hero.description = payload.description.strip()
        hero.status_text = payload.status_text.strip()
        hero.stats = {
            "brute_force": payload.brute_force,
            "bureaucracy": payload.bureaucracy,
            "soft_skills": payload.soft_skills,
            "evasion": payload.evasion,
            "hp": payload.hp,
            "max_hp": payload.max_hp,
            "stress": payload.stress,
            "max_stress": payload.max_stress,
            "scrap": payload.scrap,
        }
        hero.inventory = self._parse_inventory_text(payload.inventory_text)

        location_name = payload.current_location_name.strip()
        if location_name:
            slug = slugify(location_name)
            location = next((item for item in campaign.locations if item.slug == slug), None)
            if location is None:
                location = Location(
                    campaign_id=campaign_id,
                    slug=slug,
                    name=location_name,
                    summary="Локация задана вручную и ждет уточнения.",
                    atmosphere="",
                    danger_level="unknown",
                    notable_features=[],
                    exits=[],
                    tags=["manual"],
                )
                self.session.add(location)
                self.session.flush()
            hero.current_location = location
        else:
            hero.current_location = None

        campaign.updated_at = utcnow()
        self.session.commit()
        return self.get_campaign(campaign_id) or campaign

    @staticmethod
    def _parse_inventory_text(raw_text: str) -> list[dict]:
        items: list[dict] = []
        for line in raw_text.splitlines():
            clean = line.strip()
            if not clean:
                continue
            quantity = 1
            description = ""

            quantity_match = re.search(r"\s+x(\d+)\s*$", clean, flags=re.IGNORECASE)
            if quantity_match:
                quantity = max(int(quantity_match.group(1)), 0)
                clean = clean[: quantity_match.start()].strip()

            description_match = re.search(r"\(([^()]*)\)\s*$", clean)
            if description_match:
                description = description_match.group(1).strip()
                clean = clean[: description_match.start()].strip()

            quantity_match = re.search(r"\s+x(\d+)\s*$", clean, flags=re.IGNORECASE)
            if quantity_match:
                quantity = max(int(quantity_match.group(1)), 0)
                clean = clean[: quantity_match.start()].strip()

            items.append({"name": clean, "quantity": quantity, "description": description, "tags": []})
        return items
