from __future__ import annotations

import re
from dataclasses import dataclass

import edge_tts


DEFAULT_GEMMA_VOICE = "ru-RU-SvetlanaNeural"
_PERCENT_RE = re.compile(r"^[+-]?\d{1,3}%$")
_PITCH_RE = re.compile(r"^[+-]?\d{1,3}Hz$", re.IGNORECASE)


@dataclass(frozen=True)
class TtsSegment:
    text: str
    speaker: str = "DM"
    emotion: str = "neutral"
    rate: str | int | float = "+0%"
    pitch: str | int | float = "+0Hz"


def _normalize_percent(value: str | int | float | None, default: str = "+0%", limit: int = 45) -> str:
    if isinstance(value, int | float) and 0 < float(value) < 2:
        amount = round((float(value) - 1) * 100)
        amount = max(-limit, min(limit, amount))
        return f"{amount:+d}%"
    raw = str(value or default).strip()
    if not _PERCENT_RE.match(raw):
        raw = default
    amount = int(raw[:-1])
    amount = max(-limit, min(limit, amount))
    return f"{amount:+d}%"


def _normalize_pitch(value: str | int | float | None, default: str = "+0Hz", limit: int = 80) -> str:
    if isinstance(value, int | float) and 0 < float(value) < 2:
        amount = round((float(value) - 1) * 60)
        amount = max(-limit, min(limit, amount))
        return f"{amount:+d}Hz"
    raw = str(value or default).strip()
    if not _PITCH_RE.match(raw):
        raw = default
    amount = int(raw[:-2])
    amount = max(-limit, min(limit, amount))
    return f"{amount:+d}Hz"


def _add_percent(value: str, delta: int) -> str:
    amount = int(_normalize_percent(value)[:-1]) + delta
    amount = max(-45, min(45, amount))
    return f"{amount:+d}%"


def _add_pitch(value: str, delta: int) -> str:
    amount = int(_normalize_pitch(value)[:-2]) + delta
    amount = max(-80, min(80, amount))
    return f"{amount:+d}Hz"


def _with_speaker_tint(segment: TtsSegment) -> TtsSegment:
    speaker_text = f"{segment.speaker} {segment.text}".lower()
    speaker = segment.speaker.strip().lower()
    rate_delta = 0
    pitch_delta = 0

    emotion = segment.emotion.lower().strip()
    if emotion == "joy":
        rate_delta += 4
        pitch_delta += 10
    elif emotion == "surprised":
        rate_delta += 8
        pitch_delta += 20
    elif emotion == "angry":
        rate_delta -= 8
        pitch_delta -= 18
    elif emotion == "fear":
        rate_delta += 4
        pitch_delta += 24
    elif emotion == "shock":
        rate_delta -= 12
        pitch_delta -= 8
    elif emotion == "glasses":
        rate_delta -= 6
        pitch_delta -= 6

    if "!" in segment.text:
        rate_delta += 5
        pitch_delta += 14

    is_dm = speaker in {
        "dm",
        "gemma",
        "\u0433\u0435\u043c\u043c\u0430",
        "narrator",
        "\u0432\u0435\u0434\u0443\u0449\u0438\u0439",
        "\u0440\u0430\u0441\u0441\u043a\u0430\u0437\u0447\u0438\u043a",
    }
    if not is_dm:
        if any(word in speaker_text for word in ("\u044d\u043b\u043b\u0438", "ellie", "ally")):
            rate_delta += 8
            pitch_delta += 28
        elif any(word in speaker_text for word in ("\u043e\u0440\u043a", "\u043e\u0433\u0440", "\u0442\u0440\u043e\u043b\u043b", "\u0432\u0435\u043b\u0438\u043a\u0430\u043d", "\u0431\u0440\u0443\u0442")):
            rate_delta -= 18
            pitch_delta -= 42
        elif any(word in speaker_text for word in ("\u043b\u0438\u0447", "boss", "\u0431\u043e\u0441\u0441", "\u0434\u0435\u043c\u043e\u043d", "\u0434\u0440\u0430\u043a\u043e\u043d")):
            rate_delta -= 12
            pitch_delta -= 32
        elif any(word in speaker_text for word in ("\u0433\u043e\u0431\u043b\u0438\u043d", "\u043a\u043e\u0431\u043e\u043b\u044c\u0434", "\u0444\u0435\u044f", "\u043f\u0438\u043a\u0441\u0438")):
            rate_delta += 10
            pitch_delta += 26
        elif any(word in speaker_text for word in ("\u0441\u0435\u043a\u0440\u0435\u0442\u0430\u0440", "\u043a\u043b\u0435\u0440\u043a", "\u0430\u0443\u0434\u0438\u0442\u043e\u0440", "\u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440")):
            rate_delta -= 4
            pitch_delta += 8

    if rate_delta == 0 and pitch_delta == 0:
        return segment

    return TtsSegment(
        text=segment.text,
        speaker=segment.speaker,
        emotion=segment.emotion,
        rate=_add_percent(segment.rate, rate_delta),
        pitch=_add_pitch(segment.pitch, pitch_delta),
    )

async def synthesize_edge_tts(segment: TtsSegment, voice: str = DEFAULT_GEMMA_VOICE) -> bytes:
    tinted = _with_speaker_tint(segment)
    text = " ".join(tinted.text.split()).strip()
    if not text:
        return b""

    communicate = edge_tts.Communicate(
        text=text[:1200],
        voice=voice or DEFAULT_GEMMA_VOICE,
        rate=_normalize_percent(tinted.rate),
        pitch=_normalize_pitch(tinted.pitch),
    )
    audio_chunks: list[bytes] = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])
    return b"".join(audio_chunks)
