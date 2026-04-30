"""Coerce LLM JSON into shapes accepted by WorldDelta before Pydantic validation."""

from __future__ import annotations

from typing import Any

from .campaign_service import CampaignService


def _coerce_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if "\n" in text:
            parts = [p.strip() for p in text.splitlines() if p.strip()]
            return parts
        for sep in (";", "•"):
            if sep in text:
                return [p.strip() for p in text.split(sep) if p.strip()]
        return [text]
    return [str(value).strip()]


def _normalize_character_role(raw: str | None) -> str:
    if not raw:
        return "npc"
    s = str(raw).strip().lower()
    if s in {"npc", "enemy", "ally", "boss", "merchant"}:
        return s
    if "босс" in s or s == "boss":
        return "boss"
    if "торгов" in s or "merchant" in s:
        return "merchant"
    if "союзник" in s or "ally" in s:  # "Союзник" etc.
        return "ally"
    if "враг" in s or "enemy" in s:
        return "enemy"
    return "npc"


def _normalize_quest_kind(raw: str | None) -> str:
    if not raw:
        return "side"
    s = str(raw).strip().lower()
    if s in {"main", "side", "hazard", "deadline"}:
        return s
    if s in {"основной", "основная", "главная", "главн"}:
        return "main"
    if "основ" in s or "главн" in s:
        return "main"
    if "побоч" in s:
        return "side"
    if "опасн" in s or "hazard" in s:
        return "hazard"
    if "дедлайн" in s or "deadline" in s:
        return "deadline"
    return "side"


def _normalize_note_category(raw: str | None) -> str:
    if not raw:
        return "gm_note"
    s = str(raw).strip().lower()
    allowed = {"gm_note", "canon", "warning", "loot", "quest", "manual"}
    if s in allowed:
        return s
    if s in {"gameplay", "геймплей", "игра", "plot", "сюжет"}:
        return "gm_note"
    return "gm_note"


def _coerce_inventory_field(items: Any) -> list[dict[str, Any]]:
    if items is None:
        return []
    if isinstance(items, list) and items and all(isinstance(x, str) for x in items):
        return CampaignService._parse_inventory_text("\n".join(items))
    if isinstance(items, list):
        out: list[dict[str, Any]] = []
        for x in items:
            if isinstance(x, str):
                out.extend(CampaignService._parse_inventory_text(x))
            elif isinstance(x, dict):
                out.append(x)
        return out
    return []


def coerce_world_delta_payload(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}

    hero = data.get("hero")
    if isinstance(hero, dict) and "inventory" in hero:
        hero = {**hero, "inventory": _coerce_inventory_field(hero.get("inventory"))}
        data = {**data, "hero": hero}

    locations = data.get("locations")
    if isinstance(locations, list):
        fixed_locs = []
        for loc in locations:
            if not isinstance(loc, dict):
                continue
            nf = loc.get("notable_features")
            ex = loc.get("exits")
            loc2 = {**loc}
            if nf is not None:
                loc2["notable_features"] = _coerce_str_list(nf)
            if ex is not None:
                loc2["exits"] = _coerce_str_list(ex)
            fixed_locs.append(loc2)
        data = {**data, "locations": fixed_locs}

    characters = data.get("characters")
    if isinstance(characters, list):
        fixed_chars = []
        for ch in characters:
            if not isinstance(ch, dict):
                continue
            role = _normalize_character_role(ch.get("role"))
            inv = ch.get("inventory")
            ch2 = {**ch, "role": role}
            if inv is not None:
                ch2["inventory"] = _coerce_inventory_field(inv)
            fixed_chars.append(ch2)
        data = {**data, "characters": fixed_chars}

    quests = data.get("quests")
    if isinstance(quests, list):
        fixed_q = []
        for q in quests:
            if not isinstance(q, dict):
                continue
            kind = _normalize_quest_kind(q.get("kind"))
            fixed_q.append({**q, "kind": kind})
        data = {**data, "quests": fixed_q}

    notes = data.get("notes")
    if isinstance(notes, list):
        fixed_n = []
        for n in notes:
            if not isinstance(n, dict):
                continue
            cat = _normalize_note_category(n.get("category"))
            fixed_n.append({**n, "category": cat})
        data = {**data, "notes": fixed_n}

    return data
