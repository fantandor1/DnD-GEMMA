from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

import soundfile as sf
import torch


SILERO_LANGUAGE = "ru"
SILERO_MODEL = "v5_ru"
SILERO_SAMPLE_RATE = 48_000
KATYA_ALIASES = ("katya smirnova", "katya_smirnova", "katya-smirnova", "katya", "катя", "катя смирнова")
FALLBACK_VOICES = ("xenia", "kseniya")


@dataclass(frozen=True)
class SileroSegment:
    text: str
    speaker: str = "DM"
    emotion: str = "neutral"
    rate: str | int | float = 1.0


def _normalize_percent_rate(value: str | int | float | None) -> float:
    if isinstance(value, int | float):
        number = float(value)
        if 0.45 <= number <= 1.8:
            return number
        return max(0.55, min(1.45, 1.0 + number / 100.0))
    raw = str(value or "1.0").strip()
    if raw.endswith("%"):
        try:
            return max(0.55, min(1.45, 1.0 + int(raw[:-1]) / 100.0))
        except ValueError:
            return 1.0
    try:
        return max(0.55, min(1.45, float(raw)))
    except ValueError:
        return 1.0


def _emotion_rate(emotion: str) -> float:
    normalized = emotion.lower().strip()
    return {
        "neutral": 1.0,
        "happy": 1.06,
        "joy": 1.06,
        "amazed": 1.08,
        "surprised": 1.08,
        "shock": 1.04,
        "thinking": 0.92,
        "glasses": 0.94,
        "annoyed": 0.96,
        "angry": 0.94,
        "shy": 0.95,
        "fear": 0.97,
    }.get(normalized, 1.0)


def _speaker_rate(speaker: str, text: str) -> float:
    haystack = f"{speaker} {text}".lower()
    if any(word in haystack for word in ("элли", "ellie")):
        return 1.06
    if any(word in haystack for word in ("орк", "огр", "тролл", "великан", "брут")):
        return 0.9
    if any(word in haystack for word in ("лич", "босс", "boss", "дракон", "демон")):
        return 0.92
    if any(word in haystack for word in ("гоблин", "кобольд", "фея", "пикси")):
        return 1.08
    return 1.0


def _clean_tts_text(text: str) -> str:
    cleaned = str(text or "")
    cleaned = re.sub(r"^\s*(?:DM|LOC|NPC|НПС)\s*[:<]?\s*([^:>—-]+?)?\s*[>:—-]?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"[*_`#>]+", "", cleaned)
    cleaned = re.sub(r"\[[^\]]{0,160}\]", "", cleaned)
    cleaned = re.sub(r"\([^)]{0,160}\)\s*$", "", cleaned)
    cleaned = re.sub(r"[{}[\]]", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def _preprocess_emotion_text(text: str, emotion: str) -> str:
    cleaned = _clean_tts_text(text)
    if not cleaned:
        return ""
    normalized = emotion.lower().strip()
    if normalized in {"happy", "joy"} and not cleaned.endswith(("!", "?", "…")):
        return f"{cleaned}!"
    if normalized in {"amazed", "surprised", "shock"}:
        return cleaned.replace("...", "…")
    if normalized in {"thinking", "glasses"} and not cleaned.startswith(("Хм", "Так", "Секунду")):
        return f"Хм… {cleaned}"
    if normalized in {"shy", "fear"}:
        return cleaned.replace(",", "…")
    return cleaned


def _atempo_filter(rate: float) -> str:
    parts: list[str] = []
    remaining = rate
    while remaining > 2.0:
        parts.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        parts.append("atempo=0.5")
        remaining /= 0.5
    parts.append(f"atempo={remaining:.4f}")
    return ",".join(parts)


def _wav_bytes(audio, sample_rate: int, rate: float) -> bytes:
    normalized_rate = max(0.55, min(1.45, rate))
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        try:
            import imageio_ffmpeg

            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg = None
    if ffmpeg and abs(normalized_rate - 1.0) > 0.02:
        with tempfile.TemporaryDirectory(prefix="rpg_dm_silero_") as tmp_dir:
            src = Path(tmp_dir) / "input.wav"
            dst = Path(tmp_dir) / "output.wav"
            sf.write(str(src), audio, sample_rate, format="WAV")
            subprocess.run(
                [ffmpeg, "-y", "-loglevel", "error", "-i", str(src), "-filter:a", _atempo_filter(normalized_rate), str(dst)],
                check=True,
            )
            return dst.read_bytes()

    if not ffmpeg and abs(normalized_rate - 1.0) > 0.02:
        print("ffmpeg not found; Silero rate fallback will shift pitch slightly.", flush=True)
        import scipy.signal

        target_len = max(1, int(len(audio) / normalized_rate))
        audio = scipy.signal.resample(audio, target_len)

    buffer = io.BytesIO()
    sf.write(buffer, audio, sample_rate, format="WAV")
    return buffer.getvalue()


class SileroTTS:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loaded = False
        self._model = None
        self._speakers: list[str] = []
        self._default_voice = "xenia"

    @property
    def speakers(self) -> list[str]:
        self.load()
        return list(self._speakers)

    @property
    def default_voice(self) -> str:
        self.load()
        return self._default_voice

    def load(self) -> None:
        with self._lock:
            if self._loaded:
                return
            model, _ = torch.hub.load(
                repo_or_dir="snakers4/silero-models",
                model="silero_tts",
                language=SILERO_LANGUAGE,
                speaker=SILERO_MODEL,
                trust_repo=True,
            )
            model.to(torch.device("cpu"))
            self._model = model
            self._speakers = list(getattr(model, "speakers", []) or [])
            print(f"Silero local speakers: {', '.join(self._speakers) or '<none>'}", flush=True)
            lowered = {voice.lower(): voice for voice in self._speakers}
            katya = next((lowered[name] for name in KATYA_ALIASES if name in lowered), None)
            if katya:
                self._default_voice = katya
            else:
                fallback = next((voice for voice in FALLBACK_VOICES if voice in self._speakers), self._speakers[0] if self._speakers else "xenia")
                self._default_voice = fallback
                print("Katya Smirnova voice not found in local Silero model, using fallback voice.", flush=True)
            print(f"Silero selected voice: {self._default_voice}", flush=True)
            self._loaded = True

    def select_voice(self, requested: str | None) -> str:
        self.load()
        raw = str(requested or "").strip()
        if raw and raw in self._speakers:
            return raw
        lowered = raw.lower()
        for speaker in self._speakers:
            if speaker.lower() == lowered:
                return speaker
        return self._default_voice

    def synthesize(self, segment: SileroSegment, voice: str | None = None, rate: float | None = None) -> bytes:
        self.load()
        if self._model is None:
            raise RuntimeError("Silero model is not loaded.")
        speaker = self.select_voice(voice)
        text = _preprocess_emotion_text(segment.text, segment.emotion)
        if not text:
            return b""
        final_rate = max(0.55, min(1.45, (rate or _normalize_percent_rate(segment.rate)) * _emotion_rate(segment.emotion) * _speaker_rate(segment.speaker, text)))
        with self._lock:
            audio = self._model.apply_tts(
                text=text[:900],
                speaker=speaker,
                sample_rate=SILERO_SAMPLE_RATE,
                put_accent=True,
                put_yo=True,
            )
        if hasattr(audio, "detach"):
            audio = audio.detach().cpu().numpy()
        return _wav_bytes(audio, SILERO_SAMPLE_RATE, final_rate)


_SILERO_TTS = SileroTTS()


def get_silero_tts() -> SileroTTS:
    return _SILERO_TTS
