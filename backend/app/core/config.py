from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    app_env: str = "development"
    frontend_origin: str = "http://localhost:5173"
    jwt_secret: str
    jwt_refresh_secret: str
    quota_bytes: int = 100 * 1024 * 1024

    mongodb_uri: str = ""
    mongodb_db: str = "viva_agent"

    storage_endpoint: str = ""
    storage_region: str = "ap-south-1"
    storage_bucket: str = "viva-artifacts"
    storage_access_key: str = ""
    storage_secret_key: str = ""

    llm_provider: str = "replay"  # mock | replay | gemini
    gemini_api_key: str = ""
    gemini_force_ipv4: bool = True
    llm_model_chain: str = "gemini-3.8-flash,gemini-3.5-flash,gemini-3.5-flash-lite"
    llm_replay_dir: str = "fixtures/llm"

    embedding_provider: str = "gemini"  # gemini | mock
    embedding_model: str = "gemini-embedding-001"
    embedding_dim: int = 768

    @property
    def model_chain(self) -> list[str]:
        return [m.strip() for m in self.llm_model_chain.split(",") if m.strip()]

    @property
    def replay_path(self) -> Path:
        return BACKEND_DIR / self.llm_replay_dir


@lru_cache
def get_settings() -> Settings:
    return Settings()
