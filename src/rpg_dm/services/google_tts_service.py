from __future__ import annotations

import base64
import io
import re
import wave
from dataclasses import dataclass

import httpx
from google import genai
from google.genai import types

from ..config import Settings


DEFAULT_GOOGLE_TTS_MODEL = "gemini-3.1-flash-tts-preview"
DEFAULT_GOOGLE_TTS_VOICE = "Leda"
PCM_SAMPLE_RATE = 24_000
GOOGLE_TTS_VOICE_PROFILE = (
    "A gentle, soft-spoken female tabletop RPG narrator. She is introverted, a bit awkward, "
    "polite and friendly, with a warm shy vocal smile, natural conversational pacing, "
    "and just a tiny hint of uncertainty."
)


class GoogleTtsError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class GoogleTtsSegment:
    text: str
    speaker: str = "DM"
    emotion: str = "neutral"


def _configured_api_keys(settings: Settings, api_key_override: str | None = None) -> list[str]:
    raw_values = [api_key_override, settings.gemini_tts_api_key, settings.gemini_tts_api_keys]
    keys: list[str] = []
    for raw in raw_values:
        for key in re.split(r"[\s,;]+", str(raw or "")):
            normalized = key.strip()
            if normalized and normalized not in keys:
                keys.append(normalized)
    return keys


def _clean_visible_tts_text(text: str) -> str:
    cleaned = str(text or "")
    cleaned = re.sub(r"^\s*(?:DM|LOC)\s*:\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"^\s*(?:NPC|НПС)\s*[:<]?\s*([^:>—-]+?)\s*[>:—-]\s*", r"\1. ", cleaned, flags=re.I)
    cleaned = re.sub(r"[*_`#]+", "", cleaned)
    cleaned = re.sub(r"\([^)]{0,160}\)\s*$", "", cleaned)
    cleaned = re.sub(r"[{}]", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def _status_from_google_error(exc: Exception) -> int:
    message = str(exc).lower()
    if "429" in message or "resource_exhausted" in message or "quota" in message:
        return 429
    if "400" in message or "invalid_argument" in message:
        return 400
    if "403" in message or "permission_denied" in message or "forbidden" in message:
        return 403
    return 502


def _is_quota_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "429",
            "resource_exhausted",
            "quota",
            "rate limit",
            "too many requests",
            "exceeded",
        )
    )


def _emotion_direction(emotion: str, text: str) -> str:
    normalized = str(emotion or "neutral").lower().strip()
    has_exclaim = "!" in text
    direction = {
        "neutral": "calm and gentle",
        "joy": "warmer and quietly pleased",
        "happy": "warmer and quietly pleased",
        "surprised": "slightly surprised, but not loud",
        "amazed": "slightly amazed, but not loud",
        "shock": "startled for a moment, then controlled",
        "angry": "dry, restrained and mildly annoyed",
        "annoyed": "dry, restrained and mildly annoyed",
        "fear": "soft, cautious and a little tense",
        "shy": "soft, hesitant and shy",
        "glasses": "thoughtful, precise and focused",
        "thinking": "thoughtful, precise and focused",
    }.get(normalized, "calm and gentle")
    if has_exclaim:
        direction = f"{direction}; allow a little more energy, but keep the delivery natural"
    return direction


def _speaker_direction(segment: GoogleTtsSegment) -> str:
    haystack = f"{segment.speaker} {segment.text}".lower()
    speaker = segment.speaker.strip()
    if speaker.lower() in {"dm", "gemma", "гемма", "narrator", "ведущий", "рассказчик"}:
        return "Warm narrator tone."
    if any(word in haystack for word in ("элли", "ellie", "ally")):
        return "For this named speaker, use a slightly brighter and warmer tone."
    if any(word in haystack for word in ("орк", "огр", "тролл", "великан", "брут")):
        return "For this named speaker, use a little lower and slower tone."
    if any(word in haystack for word in ("лич", "boss", "босс", "дракон", "демон")):
        return "For this named speaker, use a colder and more formal tone."
    if any(word in haystack for word in ("гоблин", "кобольд", "фея", "пикси")):
        return "For this named speaker, use a little quicker and sharper tone."
    if any(word in haystack for word in ("секретар", "клерк", "аудитор", "менеджер", "hr")):
        return "For this named speaker, use a precise and dry office tone."
    return f"For the named speaker {speaker}, vary tone slightly but keep it natural."


def _build_prompt(segment: GoogleTtsSegment) -> str:
    text = _clean_visible_tts_text(segment.text)
    emotion_direction = _emotion_direction(segment.emotion, text)
    speaker_direction = _speaker_direction(segment)
    return (
        "Read the following transcript based on the director's note.\n\n"
        "# Director's note\n"
        "Style: The Vocal Smile. Keep the tone bright, warm, gentle and inviting. "
        "Pace: natural conversational pace with light hesitations. Accent: neutral. "
        f"Emotion for this passage: {emotion_direction}. {speaker_direction} "
        "When the transcript contains named dialogue like 'Элли:' or 'Орк:', keep the same base voice but act the character with clear changes in energy, pace and tone. "
        "Do not repeat the speaker name more than it appears in the transcript. "
        "Read the entire transcript through the final sentence; do not stop early. "
        "Read only the transcript. Do not add labels, names, markdown, JSON, asterisks, or extra commentary. "
        "If the transcript contains bracketed performance tags or SSML-like pauses, treat them only as acting direction and do not read tag names aloud. "
        "Preserve natural Russian stutters such as 'п-привет' when they appear.\n\n"
        "## Sample Context:\n"
        f"{GOOGLE_TTS_VOICE_PROFILE}\n\n"
        "## Transcript:\n"
        f"{text}"
    )


def _safety_settings() -> list[types.SafetySetting]:
    return [
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        ),
    ]


def _extract_audio_bytes(response: object) -> tuple[bytes, str]:
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            inline_data = getattr(part, "inline_data", None)
            data = getattr(inline_data, "data", None)
            if not data:
                continue
            mime_type = getattr(inline_data, "mime_type", "") or ""
            if isinstance(data, str):
                return base64.b64decode(data), mime_type
            return bytes(data), mime_type
    prompt_feedback = getattr(response, "prompt_feedback", None)
    block_reason = getattr(prompt_feedback, "block_reason", None)
    if block_reason:
        raise GoogleTtsError(f"Google TTS заблокировал аудио-профиль: {block_reason}.")
    raise GoogleTtsError("Google TTS вернул ответ без аудио.")


def _as_wav(audio_bytes: bytes, mime_type: str) -> bytes:
    if audio_bytes.startswith(b"RIFF"):
        return audio_bytes
    if "wav" in (mime_type or "").lower():
        return audio_bytes

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(PCM_SAMPLE_RATE)
        wav.writeframes(audio_bytes)
    return buffer.getvalue()


def _request_google_tts_once(
    settings: Settings,
    segment: GoogleTtsSegment,
    api_key: str,
    voice: str | None = None,
    model_override: str | None = None,
) -> bytes:
    text = _clean_visible_tts_text(segment.text)
    if not text:
        return b""

    model = (model_override or settings.gemini_tts_model or DEFAULT_GOOGLE_TTS_MODEL).strip()
    voice_name = (voice or settings.gemini_tts_voice or DEFAULT_GOOGLE_TTS_VOICE).strip()
    prompt = _build_prompt(GoogleTtsSegment(text=text, speaker=segment.speaker, emotion=segment.emotion))
    proxy_url = settings.gemini_api_proxy_url.strip() or None
    client_args: dict[str, object] = {"trust_env": False}
    if proxy_url:
        client_args["proxy"] = proxy_url

    try:
        with httpx.Client(timeout=120.0, **client_args) as http_client:
            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(
                    api_version="v1beta",
                    timeout=120_000,
                    httpx_client=http_client,
                ),
            )
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=1,
                    response_modalities=["AUDIO"],
                    safety_settings=_safety_settings(),
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice_name,
                            )
                        )
                    ),
                ),
            )
    except Exception as exc:
        raise GoogleTtsError(str(exc), status_code=_status_from_google_error(exc)) from exc

    audio_bytes, mime_type = _extract_audio_bytes(response)
    return _as_wav(audio_bytes, mime_type)


def _request_google_tts(
    settings: Settings,
    segment: GoogleTtsSegment,
    voice: str | None = None,
    model_override: str | None = None,
    api_key_override: str | None = None,
) -> bytes:
    keys = _configured_api_keys(settings, api_key_override)
    if not keys:
        raise GoogleTtsError("Для Google TTS не задан RPG_DM_GEMINI_TTS_API_KEY или RPG_DM_GEMINI_TTS_API_KEYS в .env.")

    quota_errors: list[str] = []
    for index, api_key in enumerate(keys, start=1):
        try:
            return _request_google_tts_once(settings, segment, api_key, voice, model_override)
        except GoogleTtsError as exc:
            if exc.status_code == 429 or _is_quota_error(exc):
                quota_errors.append(f"ключ {index}/{len(keys)}: {exc}")
                continue
            raise

    detail = quota_errors[-1] if quota_errors else "нет доступных ключей"
    raise GoogleTtsError(f"Все ключи Google TTS упёрлись в лимит. Последняя ошибка: {detail}", status_code=429)


def synthesize_google_tts(
    settings: Settings,
    segment: GoogleTtsSegment,
    voice: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> bytes:
    return _request_google_tts(settings, segment, voice, model, api_key)
