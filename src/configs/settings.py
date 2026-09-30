from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / ".env"


class CoreSetting(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OLLAMA_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model_name: str = "qwen3.8:latest"
    model_url: str = "http://192.168.1.111:11434"


settings = CoreSetting()
