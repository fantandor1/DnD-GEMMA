from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


def _default_database_path() -> Path:
    if os.environ.get("VERCEL") or os.environ.get("RPG_DM_EPHEMERAL_DB") == "1":
        return Path(os.environ.get("TMPDIR", "/tmp")) / "rpg_memory_dm.sqlite3"
    return BASE_DIR / "data" / "rpg_memory_dm.sqlite3"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        env_prefix="RPG_DM_",
        extra="ignore",
    )

    app_name: str = "RPG Memory DM"
    host: str = "127.0.0.1"
    port: int = 8008
    lm_studio_base_url: str = "http://127.0.0.1:1234/v1"
    lm_studio_api_key: str = ""
    gemini_api_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_api_key: str = ""
    gemini_tts_api_key: str = ""
    gemini_tts_api_keys: str = ""
    gemini_tts_model: str = "gemini-3.1-flash-tts-preview"
    gemini_tts_voice: str = "Leda"
    gemini_api_proxy_url: str = ""
    default_model: str = "google/gemma-4-e4b"
    database_path: Path = Field(default_factory=_default_database_path)
    narrative_temperature: float = 0.85
    narrative_max_tokens: int = 4096
    memory_temperature: float = 0.2
    memory_max_tokens: int = 2048
    recent_turn_window: int = 10
    prompt_location_limit: int = 6
    prompt_character_limit: int = 8
    prompt_note_limit: int = 6

    recap_enabled: bool = True
    recap_turn_window: int = 18
    recap_temperature: float = 0.15
    recap_max_tokens: int = 900
    recap_trigger_context_tokens: int = 50000
    recap_keep_last_turns: int = 2

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path.as_posix()}"

    @property
    def normalized_lm_studio_base_url(self) -> str:
        value = self.lm_studio_base_url.strip().rstrip("/")
        if not value.startswith(("http://", "https://")):
            value = f"http://{value}"
        return value

    @property
    def normalized_gemini_api_base_url(self) -> str:
        return self.gemini_api_base_url.strip().rstrip("/")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
