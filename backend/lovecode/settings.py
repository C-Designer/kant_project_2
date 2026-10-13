from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LC_", env_file=".env", extra="ignore")
    api_enabled: bool = False
    provider: str = "unconfigured"
    api_key: str = ""
    model: str = ""
    real_analysis_enabled: bool = False
    classifier_mode: str = "openai"
    models_dir: str = "artifacts/models/comparison-v1"
    allowed_origins: str = "http://127.0.0.1:3100,http://localhost:3100"
    daily_analysis_limit: int = 20
    analysis_wait_seconds: float = Field(default=30, gt=0, le=45)
    analysis_capacity: int = Field(default=20, ge=1, le=32)
    bert_concurrency: int = Field(default=2, ge=1, le=2)
    explanation_concurrency: int = Field(default=5, ge=1, le=10)
    demo_enabled: bool = True
    rate_limit_enabled: bool = True


@lru_cache
def settings():
    return Settings()
