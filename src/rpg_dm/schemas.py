from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class InventoryItemPayload(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    quantity: int = Field(default=1, ge=0, le=999)
    description: str = ""
    tags: list[str] = Field(default_factory=list)


class LocationDelta(StrictModel):
    name: str = Field(min_length=1, max_length=220)
    summary: str
    atmosphere: str = ""
    danger_level: str = "unknown"
    group_path: str | None = None
    notable_features: list[str] = Field(default_factory=list)
    exits: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class CharacterDelta(StrictModel):
    name: str = Field(min_length=1, max_length=220)
    role: Literal["npc", "enemy", "ally", "boss", "merchant"] = "npc"
    location_name: str | None = None
    summary: str = ""
    personality: str = ""
    status: str = "active"
    attitude: str = "neutral"
    is_alive: bool = True
    stats: dict[str, int | str | float] = Field(default_factory=dict)
    inventory: list[InventoryItemPayload] = Field(default_factory=list)


class QuestDelta(StrictModel):
    title: str = Field(min_length=1, max_length=220)
    description: str = ""
    kind: Literal["main", "side", "hazard", "deadline"] = "side"
    status: Literal["active", "completed", "failed", "paused"] = "active"
    progress_note: str = ""
    turns_remaining: int | None = Field(default=None, ge=0, le=999)
    turns_total: int | None = Field(default=None, ge=1, le=999)
    auto_decrement: bool = False


class NoteDelta(StrictModel):
    title: str = Field(min_length=1, max_length=220)
    body: str = ""
    category: Literal["gm_note", "canon", "warning", "loot", "quest", "manual"] = "gm_note"
    importance: Literal["low", "medium", "high"] = "medium"
    is_pinned: bool = False
    action: Literal["upsert", "delete"] = "upsert"


class HeroDelta(StrictModel):
    name: str | None = None
    archetype: str | None = None
    description: str | None = None
    status_text: str | None = None
    current_location_name: str | None = None
    stats: dict[str, int | str | float] = Field(default_factory=dict)
    inventory: list[InventoryItemPayload] = Field(default_factory=list)


class WorldDelta(StrictModel):
    current_location_name: str | None = None
    hero: HeroDelta = Field(default_factory=HeroDelta)
    locations: list[LocationDelta] = Field(default_factory=list)
    characters: list[CharacterDelta] = Field(default_factory=list)
    quests: list[QuestDelta] = Field(default_factory=list)
    notes: list[NoteDelta] = Field(default_factory=list)


class CampaignCreatePayload(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    setting_name: str = Field(min_length=1, max_length=200)
    goal: str = Field(min_length=1)
    tone: str = Field(default="")
    system_prompt: str = Field(min_length=1)
    model_id: str | None = None
    hero_name: str = Field(min_length=1, max_length=120)
    hero_archetype: str = Field(min_length=1, max_length=200)
    hero_description: str = Field(min_length=1)
    hero_inventory_text: str = ""
    brute_force: int = Field(default=0, ge=-5, le=10)
    bureaucracy: int = Field(default=0, ge=-5, le=10)
    soft_skills: int = Field(default=0, ge=-5, le=10)
    evasion: int = Field(default=0, ge=-5, le=10)
    hp: int = Field(default=20, ge=0, le=999)
    max_hp: int = Field(default=20, ge=1, le=999)
    stress: int = Field(default=0, ge=0, le=20)
    max_stress: int = Field(default=7, ge=1, le=20)
    scrap: int = Field(default=0, ge=0, le=999)


class CampaignUpdatePayload(StrictModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    setting_name: str | None = Field(default=None, min_length=1, max_length=200)
    goal: str | None = Field(default=None, min_length=1)
    tone: str | None = None
    system_prompt: str | None = Field(default=None, min_length=1)
    model_id: str | None = None


class HeroUpdatePayload(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    archetype: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    status_text: str = ""
    current_location_name: str = ""
    inventory_text: str = ""
    brute_force: int = Field(default=0, ge=-5, le=10)
    bureaucracy: int = Field(default=0, ge=-5, le=10)
    soft_skills: int = Field(default=0, ge=-5, le=10)
    evasion: int = Field(default=0, ge=-5, le=10)
    hp: int = Field(default=20, ge=0, le=999)
    max_hp: int = Field(default=20, ge=1, le=999)
    stress: int = Field(default=0, ge=0, le=20)
    max_stress: int = Field(default=7, ge=1, le=20)
    scrap: int = Field(default=0, ge=0, le=999)


class CampaignImportPayload(StrictModel):
    transcript: str = Field(min_length=1)
    create_note: bool = False
    note_title: str = Field(default="Импорт старой партии", min_length=1, max_length=220)
    show_chat_summary: bool = True
    api_key: str | None = Field(default=None, max_length=220)


class MessageRequest(StrictModel):
    message: str = Field(min_length=1)
    dice_result: int | None = Field(default=None, ge=1, le=20)
    api_key: str | None = Field(default=None, max_length=220)


class NoteCreatePayload(StrictModel):
    title: str = Field(min_length=1, max_length=220)
    body: str = Field(min_length=1)
    category: Literal["manual", "gm_note", "canon", "warning", "quest", "loot"] = "manual"
    importance: Literal["low", "medium", "high"] = "medium"
    is_pinned: bool = True


class TtsSegmentPayload(StrictModel):
    line: int | None = Field(default=None, ge=1, le=999)
    text: str = Field(min_length=1, max_length=6000)
    speaker: str = Field(default="DM", max_length=80)
    emotion: str = Field(default="neutral", max_length=32)
    rate: str | int | float = "+0%"
    pitch: str | int | float = "+0Hz"
    pause_ms: int = Field(default=220, ge=0, le=2500, alias="pauseMs")


class TtsRequestPayload(StrictModel):
    segment: TtsSegmentPayload
    voice: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    api_key: str | None = Field(default=None, max_length=220)
