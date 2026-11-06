"""Application settings, read from environment variables (prefix AGENTLAB_) or a .env file."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AGENTLAB_", extra="ignore")

    database_url: str = f"sqlite:///{(BASE_DIR / 'agentlab.db').as_posix()}"
    data_dir: Path = BASE_DIR / "data"

    # Model servers. Ollama uses its native API, the others speak the OpenAI chat API.
    ollama_url: str = "http://localhost:11434"
    llamacpp_url: str = "http://localhost:8080/v1"
    nim_url: str = "https://integrate.api.nvidia.com/v1"
    nim_api_key: str = ""
    openai_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""

    request_timeout_s: float = 180.0
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


def get_settings() -> Settings:
    return Settings()
