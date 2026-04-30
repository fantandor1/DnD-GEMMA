from __future__ import annotations

import json
import re
import time
from typing import Any, Callable

import httpx

from ..config import Settings
from ..models import Campaign
from ..prompts import (
    MEMORY_IMPORT_SYSTEM_PROMPT,
    MEMORY_EXTRACTION_SYSTEM_PROMPT,
    build_memory_import_user_prompt,
    build_memory_extraction_fallback_user_prompt,
    build_memory_extraction_user_prompt,
    build_narrative_system_prompt,
    build_player_turn_content,
    STORY_RECAP_SYSTEM_PROMPT,
)
from ..schemas import InventoryItemPayload, WorldDelta
from .serialization import build_memory_block, recent_turn_messages
from ..utils import compact_text, estimate_tokens
from .world_delta_coerce import coerce_world_delta_payload

GOOGLE_API_MODEL_PREFIX = "googleapi/"
LEGACY_GEMINI_MODEL_PREFIX = "gemini/"
GOOGLE_API_FALLBACK_MODELS = [
    "googleapi/gemma-4-31b-it",
    "googleapi/gemini-3.1-pro",
    "googleapi/gemini-2.5-flash-lite",
    "googleapi/gemini-2.5-flash",
]
DM_SYSTEM_BLOCK_PATTERN = re.compile(r"\[DM_SYSTEM\]\s*(?P<payload>\{.*?\})\s*\[/DM_SYSTEM\]", re.IGNORECASE | re.DOTALL)


class LMStudioError(RuntimeError):
    pass


class MemoryExtractionError(RuntimeError):
    def __init__(self, message: str, raw_payload: str = "") -> None:
        super().__init__(message)
        self.raw_payload = raw_payload


class LMStudioClient:
    def __init__(self, settings: Settings, gemini_api_key: str | None = None) -> None:
        self.settings = settings
        self.gemini_api_key_override = (gemini_api_key or "").strip()

    def _effective_gemini_api_key(self) -> str:
        return self.gemini_api_key_override or self.settings.gemini_api_key.strip()

    def _build_headers(self) -> dict[str, str]:
        if not self.settings.lm_studio_api_key.strip():
            return {}
        return {"Authorization": f"Bearer {self.settings.lm_studio_api_key.strip()}"}

    def _make_client(self, timeout: float) -> httpx.Client:
        return httpx.Client(
            timeout=timeout,
            headers=self._build_headers(),
            trust_env=False,
            http2=False,
        )

    def _make_gemini_client(self, timeout: float) -> httpx.Client:
        proxy_url = self.settings.gemini_api_proxy_url.strip() or None
        return httpx.Client(
            timeout=timeout,
            headers={
                "x-goog-api-key": self._effective_gemini_api_key(),
                "Content-Type": "application/json",
            },
            proxy=proxy_url,
            trust_env=False,
            http2=False,
        )

    @staticmethod
    def _is_google_api_model(model_id: str) -> bool:
        return model_id.startswith((GOOGLE_API_MODEL_PREFIX, LEGACY_GEMINI_MODEL_PREFIX))

    @staticmethod
    def _normalize_google_api_model_name(model_name: str) -> str:
        clean = model_name.strip()
        if clean.startswith("models/"):
            clean = clean.split("/", 1)[1]
        if clean.startswith((GOOGLE_API_MODEL_PREFIX, LEGACY_GEMINI_MODEL_PREFIX)):
            return clean
        return f"{GOOGLE_API_MODEL_PREFIX}{clean}"

    @staticmethod
    def _google_api_provider_model(model_id: str) -> str:
        if model_id.startswith((GOOGLE_API_MODEL_PREFIX, LEGACY_GEMINI_MODEL_PREFIX)):
            return model_id.split("/", 1)[1]
        return model_id

    def list_models(self) -> list[str]:
        seen: set[str] = set()
        combined: list[str] = []
        for model_id in self._list_lm_studio_models() + self._list_gemini_models():
            if model_id in seen:
                continue
            seen.add(model_id)
            combined.append(model_id)
        return combined

    def _list_lm_studio_models(self) -> list[str]:
        try:
            with self._make_client(timeout=10.0) as client:
                response = client.get(f"{self.settings.normalized_lm_studio_base_url}/models")
                response.raise_for_status()
            payload = response.json()
        except Exception:
            return []

        return [item["id"] for item in payload.get("data", []) if item.get("id")]

    def _list_gemini_models(self) -> list[str]:
        if not self._effective_gemini_api_key():
            return list(GOOGLE_API_FALLBACK_MODELS)
        try:
            with self._make_gemini_client(timeout=15.0) as client:
                response = client.get(f"{self.settings.normalized_gemini_api_base_url}/models", params={"pageSize": 1000})
                response.raise_for_status()
            payload = response.json()
            models: list[str] = []
            for item in payload.get("models", []):
                name = item.get("name") or ""
                methods = item.get("supportedGenerationMethods") or []
                if "generateContent" not in methods:
                    continue
                if "embedding" in name.lower():
                    continue
                models.append(self._normalize_google_api_model_name(name))
            return models or list(GOOGLE_API_FALLBACK_MODELS)
        except Exception:
            return list(GOOGLE_API_FALLBACK_MODELS)

    @classmethod
    def _validate_world_delta(cls, payload: dict[str, Any]) -> WorldDelta:
        return WorldDelta.model_validate(coerce_world_delta_payload(payload))

    def generate_narrative(
        self,
        campaign: Campaign,
        player_message: str,
        dice_result: int | None,
    ) -> str:
        memory_block = build_memory_block(campaign, self.settings)
        messages = [{"role": "system", "content": build_narrative_system_prompt(campaign, campaign.hero, memory_block)}]
        messages.extend(recent_turn_messages(campaign, self.settings.recent_turn_window))
        messages.append({"role": "user", "content": build_player_turn_content(player_message, dice_result)})

        content, _ = self._chat_completion(
            model_id=campaign.model_id,
            messages=messages,
            temperature=self.settings.narrative_temperature,
            max_tokens=self.settings.narrative_max_tokens,
        )
        return content.strip()

    def estimate_narrative_prompt_tokens(
        self,
        campaign: Campaign,
        player_message: str,
        dice_result: int | None,
    ) -> int:
        memory_block = build_memory_block(campaign, self.settings)
        system = build_narrative_system_prompt(campaign, campaign.hero, memory_block)
        recent = recent_turn_messages(campaign, self.settings.recent_turn_window)
        user = build_player_turn_content(player_message, dice_result)

        total = estimate_tokens(system) + estimate_tokens(user)
        for msg in recent:
            total += estimate_tokens(msg.get("content", ""))
        return total

    def generate_story_recap(
        self,
        campaign: Campaign,
        *,
        previous_recap: str,
    ) -> str:
        memory_block = build_memory_block(campaign, self.settings)
        turns = campaign.turns[-self.settings.recap_turn_window :]
        lines: list[str] = []
        for turn in turns:
            if turn.role not in {"user", "assistant"}:
                continue
            prefix = "Игрок" if turn.role == "user" else "DM"
            text = compact_text(turn.content or "", 900 if turn.role == "assistant" else 600)
            if turn.role == "user" and turn.dice_result is not None:
                text = f"{text} (d20={turn.dice_result})"
            if text:
                lines.append(f"{prefix}: {text}")

        transcript = "\n".join(lines).strip()
        user_prompt_parts = [
            "[КАНОН (кратко)]",
            memory_block,
        ]
        if previous_recap.strip():
            user_prompt_parts.extend(["", "[ПРЕДЫДУЩЕЕ_РЕЗЮМЕ]", previous_recap.strip()])
        user_prompt_parts.extend(["", "[ПОСЛЕДНИЕ_СООБЩЕНИЯ]", transcript or "Нет сообщений."])

        messages = [
            {"role": "system", "content": STORY_RECAP_SYSTEM_PROMPT},
            {"role": "user", "content": "\n".join(user_prompt_parts).strip()},
        ]

        content, _ = self._chat_completion(
            model_id=campaign.model_id,
            messages=messages,
            temperature=self.settings.recap_temperature,
            max_tokens=self.settings.recap_max_tokens,
        )
        return content.strip()

    @staticmethod
    def sanitize_narrative(content: str) -> str:
        cleaned = (content or "").strip()
        cleaned = DM_SYSTEM_BLOCK_PATTERN.sub("", cleaned)
        cleaned = re.sub(r"\n?\*{3,}\s*\n+\*{0,2}HUD\*{0,2}.*$", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        return cleaned or (content or "").strip()

    @classmethod
    def _extract_inline_world_delta(cls, assistant_message: str) -> tuple[WorldDelta | None, str, str]:
        match = DM_SYSTEM_BLOCK_PATTERN.search(assistant_message or "")
        if not match:
            return None, "", ""

        raw_payload = (match.group("payload") or "").strip()
        if not raw_payload:
            return None, "", "DM_SYSTEM блок пустой."

        try:
            payload = cls._parse_json_object(raw_payload)
            return cls._validate_world_delta(payload), raw_payload, ""
        except Exception as exc:
            return None, raw_payload, f"DM_SYSTEM блок не прошел валидацию: {exc}"

    @staticmethod
    def _merge_model_delta(base_model: Any, overlay_model: Any) -> Any:
        result = base_model.model_copy(deep=True)
        for field_name in overlay_model.model_fields_set:
            overlay_value = getattr(overlay_model, field_name)
            base_value = getattr(result, field_name, None)
            if isinstance(base_value, dict) and isinstance(overlay_value, dict):
                merged = dict(base_value)
                merged.update(overlay_value)
                setattr(result, field_name, merged)
            else:
                setattr(result, field_name, overlay_value)
        return result

    @classmethod
    def _merge_model_list(
        cls,
        base_items: list[Any],
        overlay_items: list[Any],
        key_getter: Callable[[Any], str],
    ) -> list[Any]:
        merged: dict[str, Any] = {}
        order: list[str] = []

        for item in base_items:
            key = key_getter(item)
            if not key:
                continue
            merged[key] = item.model_copy(deep=True)
            order.append(key)

        for item in overlay_items:
            key = key_getter(item)
            if not key:
                continue
            if key in merged:
                merged[key] = cls._merge_model_delta(merged[key], item)
            else:
                merged[key] = item.model_copy(deep=True)
                order.append(key)

        return [merged[key] for key in order]

    @classmethod
    def _merge_world_delta(cls, primary: WorldDelta, overlay: WorldDelta) -> WorldDelta:
        result = primary.model_copy(deep=True)
        if "current_location_name" in overlay.model_fields_set:
            result.current_location_name = overlay.current_location_name
            result.model_fields_set.add("current_location_name")

        result.hero = cls._merge_model_delta(primary.hero, overlay.hero)
        result.locations = cls._merge_model_list(primary.locations, overlay.locations, lambda item: item.name.strip().lower())
        result.characters = cls._merge_model_list(primary.characters, overlay.characters, lambda item: item.name.strip().lower())
        result.quests = cls._merge_model_list(primary.quests, overlay.quests, lambda item: item.title.strip().lower())
        result.notes = cls._merge_model_list(primary.notes, overlay.notes, lambda item: item.title.strip().lower())
        return result

    @classmethod
    def _apply_narrative_hud_fallback(cls, delta: WorldDelta, assistant_message: str) -> WorldDelta:
        location_name = cls._extract_hud_value(assistant_message, "Локация")
        if location_name:
            delta.current_location_name = location_name
            delta.model_fields_set.add("current_location_name")
            delta.hero.current_location_name = location_name
            delta.hero.model_fields_set.add("current_location_name")

        hero_stats = dict(delta.hero.stats)
        stats_updated = False
        stress_match = re.search(r"(\d+)\s*/\s*(\d+)", cls._extract_hud_value(assistant_message, "Стресс"))
        if stress_match:
            hero_stats["stress"] = int(stress_match.group(1))
            hero_stats["max_stress"] = int(stress_match.group(2))
            stats_updated = True

        scrap_match = re.search(r"\d+", cls._extract_hud_value(assistant_message, "Металлолом"))
        if scrap_match:
            hero_stats["scrap"] = int(scrap_match.group(0))
            stats_updated = True

        if stats_updated:
            delta.hero.stats = hero_stats
            delta.hero.model_fields_set.add("stats")

        inventory_line = cls._extract_hud_value(assistant_message, "Инвентарь")
        parsed_inventory = cls._parse_hud_inventory(inventory_line)
        if parsed_inventory:
            delta.hero.inventory = parsed_inventory
            delta.hero.model_fields_set.add("inventory")

        return delta

    @staticmethod
    def _extract_hud_value(text: str, label: str) -> str:
        for line in (text or "").splitlines():
            normalized = re.sub(r"\*+", "", line).strip()
            if not normalized:
                continue
            if normalized.lower().startswith(f"{label.lower()}:"):
                return normalized.split(":", 1)[1].strip()
        return ""

    @staticmethod
    def _parse_hud_inventory(text: str) -> list[InventoryItemPayload]:
        cleaned = re.sub(r"\*+", "", (text or "")).strip()
        if not cleaned or cleaned.lower() in {"пусто", "ничего", "нет"}:
            return []

        parts = [
            fragment.strip().lstrip("-• ").strip()
            for fragment in re.split(r"\s*(?:,|;|\n)\s*", cleaned)
            if fragment.strip()
        ]
        items: list[InventoryItemPayload] = []
        for part in parts:
            quantity = 1
            description = ""

            quantity_match = re.search(r"\s+x(\d+)$", part, flags=re.IGNORECASE)
            if quantity_match:
                quantity = int(quantity_match.group(1))
                part = part[: quantity_match.start()].strip()

            description_match = re.search(r"\(([^()]*)\)\s*$", part)
            if description_match:
                description = description_match.group(1).strip()
                part = part[: description_match.start()].strip()

            if not part:
                continue
            items.append(
                InventoryItemPayload(
                    name=part,
                    quantity=quantity,
                    description=description,
                    tags=[],
                )
            )
        return items

    def extract_world_delta(
        self,
        campaign: Campaign,
        player_message: str,
        dice_result: int | None,
        assistant_message: str,
    ) -> tuple[WorldDelta, str]:
        memory_block = build_memory_block(campaign, self.settings)
        schema = self._normalize_schema(WorldDelta.model_json_schema())
        inline_delta, inline_raw, inline_error = self._extract_inline_world_delta(assistant_message)

        messages = [
            {"role": "system", "content": MEMORY_EXTRACTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_memory_extraction_user_prompt(
                    campaign,
                    campaign.hero,
                    memory_block,
                    player_message,
                    dice_result,
                    assistant_message,
                ),
            },
        ]

        structured_error = ""
        structured_raw = ""
        try:
            delta, raw_payload = self._extract_world_delta_with_schema(campaign.model_id, messages, schema)
            if inline_delta is not None:
                delta = self._merge_world_delta(delta, inline_delta)
            return self._apply_narrative_hud_fallback(delta, assistant_message), raw_payload
        except (LMStudioError, MemoryExtractionError) as exc:
            structured_error = str(exc)
            structured_raw = getattr(exc, "raw_payload", "")

        fallback_messages = [
            {"role": "system", "content": MEMORY_EXTRACTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_memory_extraction_fallback_user_prompt(
                    campaign,
                    campaign.hero,
                    memory_block,
                    player_message,
                    dice_result,
                    assistant_message,
                    schema,
                ),
            },
        ]
        fallback_error = ""
        fallback_raw = ""
        try:
            delta, raw_payload = self._extract_world_delta_with_prompt(campaign.model_id, fallback_messages)
            if inline_delta is not None:
                delta = self._merge_world_delta(delta, inline_delta)
            return self._apply_narrative_hud_fallback(delta, assistant_message), raw_payload
        except (LMStudioError, MemoryExtractionError) as exc:
            fallback_error = str(exc)
            fallback_raw = getattr(exc, "raw_payload", "")

        if inline_delta is not None:
            return self._apply_narrative_hud_fallback(inline_delta, assistant_message), inline_raw

        details = " | ".join(part for part in (structured_error, fallback_error, inline_error) if part)
        raise MemoryExtractionError(
            f"Не удалось обновить память мира: {details or 'модель не вернула валидный JSON'}",
            raw_payload=fallback_raw or structured_raw or inline_raw,
        )

    def import_world_delta_from_transcript(
        self,
        campaign: Campaign,
        transcript: str,
    ) -> tuple[WorldDelta, str]:
        memory_block = build_memory_block(campaign, self.settings)
        schema = self._normalize_schema(WorldDelta.model_json_schema())
        messages = [
            {"role": "system", "content": MEMORY_IMPORT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_memory_import_user_prompt(
                    campaign,
                    campaign.hero,
                    memory_block,
                    transcript,
                    schema,
                ),
            },
        ]
        return self._extract_world_delta_with_prompt(campaign.model_id, messages)

    def _extract_world_delta_with_schema(
        self,
        model_id: str,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
    ) -> tuple[WorldDelta, str]:
        attempts = [self.settings.memory_max_tokens, self.settings.memory_max_tokens + 180]
        last_error = ""
        last_raw = ""
        for token_budget in attempts:
            raw_content, finish_reason = self._chat_completion(
                model_id=model_id,
                messages=messages,
                temperature=self.settings.memory_temperature,
                max_tokens=token_budget,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "world_delta",
                        "strict": True,
                        "schema": schema,
                    },
                },
            )
            last_raw = raw_content
            if finish_reason == "length":
                last_error = "Structured output памяти обрезался по лимиту токенов."
                continue
            try:
                payload = self._parse_json_object(raw_content)
                return self._validate_world_delta(payload), raw_content
            except Exception as exc:
                last_error = str(exc)

        raise MemoryExtractionError(
            f"Structured output памяти не прошел валидацию: {last_error or 'пустой ответ'}",
            raw_payload=last_raw,
        )

    def _extract_world_delta_with_prompt(
        self,
        model_id: str,
        messages: list[dict[str, str]],
    ) -> tuple[WorldDelta, str]:
        attempts = [
            self.settings.memory_max_tokens + 360,
            self.settings.memory_max_tokens + 1600,
            self.settings.memory_max_tokens + 3600,
        ]
        last_raw = ""
        last_err = ""
        for token_budget in attempts:
            raw_content, finish_reason = self._chat_completion(
                model_id=model_id,
                messages=messages,
                temperature=min(self.settings.memory_temperature, 0.1),
                max_tokens=token_budget,
            )
            last_raw = raw_content
            if finish_reason == "length":
                last_err = "Fallback-режим памяти обрезался по лимиту токенов."
                continue
            try:
                payload = self._parse_json_object(raw_content)
                return self._validate_world_delta(payload), raw_content
            except Exception as exc:
                last_err = f"Fallback-режим памяти вернул невалидный JSON: {exc}"

        raise MemoryExtractionError(
            last_err or "Fallback-режим памяти не дал валидный JSON.",
            raw_payload=last_raw,
        )

    def _chat_completion(
        self,
        *,
        model_id: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: dict[str, Any] | None = None,
    ) -> tuple[str, str | None]:
        if self._is_google_api_model(model_id):
            return self._chat_completion_gemini(
                model_id=model_id,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )

        payload: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        try:
            with self._make_client(timeout=120.0) as client:
                response = client.post(
                    f"{self.settings.normalized_lm_studio_base_url}/chat/completions",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            try:
                details = exc.response.json()
            except Exception:
                details = exc.response.text
            raise LMStudioError(
                f"LM Studio вернул ошибку {exc.response.status_code} по адресу "
                f"{self.settings.normalized_lm_studio_base_url}: {details or 'пустой ответ'}"
            ) from exc
        except httpx.HTTPError as exc:
            raise LMStudioError(
                "Не получилось связаться с LM Studio. Проверь адрес сервера, авторизацию и то, что локальный сервер реально принимает запросы."
            ) from exc

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = message.get("content") or ""
        finish_reason = choice.get("finish_reason")
        if not content:
            raise LMStudioError("LM Studio вернул пустой ответ.")
        return content, finish_reason

    def _chat_completion_gemini(
        self,
        *,
        model_id: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: dict[str, Any] | None = None,
    ) -> tuple[str, str | None]:
        if not self._effective_gemini_api_key():
            raise LMStudioError(
                "Для Google/Gemini API не задан ключ. В публичной версии вставь Google API key в блоке API-ключей; "
                "в локальной версии можно указать RPG_DM_GEMINI_API_KEY в .env."
            )

        system_chunks: list[str] = []
        contents: list[dict[str, Any]] = []
        for message in messages:
            role = message.get("role", "user")
            content = (message.get("content") or "").strip()
            if not content:
                continue
            if role == "system":
                system_chunks.append(content)
                continue
            gemini_role = "model" if role == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": [{"text": content}]})

        payload: dict[str, Any] = {
            "contents": contents or [{"role": "user", "parts": [{"text": "Привет."}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_chunks:
            payload["system_instruction"] = {"parts": [{"text": "\n\n".join(system_chunks)}]}
        if response_format and response_format.get("type") == "json_schema":
            payload["generationConfig"]["responseMimeType"] = "application/json"
            payload["generationConfig"]["responseJsonSchema"] = response_format["json_schema"]["schema"]

        provider_model = self._google_api_provider_model(model_id)
        if provider_model.startswith("gemini-2.5"):
            payload["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}
        elif provider_model.startswith("gemini-3"):
            payload["generationConfig"]["thinkingConfig"] = {"thinkingLevel": "low"}

        try:
            with self._make_gemini_client(timeout=120.0) as client:
                data: dict[str, Any] | None = None
                for attempt in range(3):
                    response = client.post(
                        f"{self.settings.normalized_gemini_api_base_url}/models/{provider_model}:generateContent",
                        json=payload,
                    )
                    try:
                        response.raise_for_status()
                        data = response.json()
                        break
                    except httpx.HTTPStatusError as exc:
                        if exc.response.status_code >= 500 and attempt < 2:
                            time.sleep(1.0 + attempt)
                            continue
                        raise
                if data is None:
                    raise LMStudioError("Gemini API не вернул валидный ответ.")
        except httpx.HTTPStatusError as exc:
            try:
                details = exc.response.json()
            except Exception:
                details = exc.response.text
            details_text = json.dumps(details, ensure_ascii=False) if isinstance(details, (dict, list)) else str(details)
            if exc.response.status_code == 400 and "User location is not supported for the API use." in details_text:
                raise LMStudioError(
                    "Google API видит эту модель, но не дает запускать ее из текущего региона или сетевого маршрута. "
                    "Для стабильной работы сейчас лучше использовать локальную модель через LM Studio."
                ) from exc
            raise LMStudioError(
                f"Gemini API вернул ошибку {exc.response.status_code}: {details or 'пустой ответ'}"
            ) from exc
        except httpx.HTTPError as exc:
            raise LMStudioError("Не получилось связаться с Gemini API.") from exc

        candidate = (data.get("candidates") or [{}])[0]
        content_parts = ((candidate.get("content") or {}).get("parts") or [])
        text = "".join(part.get("text", "") for part in content_parts if not part.get("thought")).strip()
        finish_reason = candidate.get("finishReason")
        if finish_reason == "MAX_TOKENS":
            finish_reason = "length"
        elif isinstance(finish_reason, str):
            finish_reason = finish_reason.lower()
        if not text:
            raise LMStudioError("Gemini API вернул пустой ответ.")
        return text, finish_reason

    @staticmethod
    def _parse_json_object(raw_text: str) -> dict[str, Any]:
        candidate = raw_text.strip()
        if candidate.startswith("```"):
            candidate = candidate.strip("`")
            if candidate.startswith("json"):
                candidate = candidate[4:]
            candidate = candidate.strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(candidate[start : end + 1])
            raise

    @staticmethod
    def _normalize_schema(schema: Any, *, preserve_property_names: bool = False) -> Any:
        if isinstance(schema, dict):
            cleaned: dict[str, Any] = {}
            for key, value in schema.items():
                if not preserve_property_names and key in {"title", "default"}:
                    continue
                child_preserve_property_names = key in {"properties", "$defs", "definitions", "patternProperties"}
                cleaned[key] = LMStudioClient._normalize_schema(
                    value,
                    preserve_property_names=child_preserve_property_names,
                )
            return cleaned
        if isinstance(schema, list):
            return [
                LMStudioClient._normalize_schema(item, preserve_property_names=preserve_property_names)
                for item in schema
            ]
        return schema
