from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / ".env"


class OllamaSettings(BaseSettings):
    """Settings cho Ollama LLM server."""

    model_config = SettingsConfigDict(
        env_prefix="OLLAMA_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model_name: str
    model_url: str


class AgentSettings(BaseSettings):
    """Settings cho agent behavior."""

    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    max_search_attempts: int = 3


ollama_settings = OllamaSettings()
agent_settings = AgentSettings()
