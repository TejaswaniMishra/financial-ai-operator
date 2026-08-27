import json
from functools import lru_cache
from typing import List, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.env import Environment


class Settings(BaseSettings):
    """Application runtime configuration and environment settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Core Application Settings
    APP_NAME: str = "Financial AI Operator"
    APP_VERSION: str = "0.1.0"
    APP_ENV: Environment = Environment.DEVELOPMENT
    DEBUG: bool = True

    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Database Configuration
    # Defaults to async SQLite file if PostgreSQL is not explicitly reachable/configured
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./finops_local.db",
        description="Async database connection string",
    )
    DATABASE_URL_SYNC: str = Field(
        default="sqlite:///./finops_local.db",
        description="Sync database connection string (for migrations and sync utilities)",
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_ECHO: bool = False

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, tuple)):
            return [str(i) for i in v]
        return ["*"]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == Environment.DEVELOPMENT

    @property
    def is_test(self) -> bool:
        return self.APP_ENV == Environment.TEST


@lru_cache()
def get_settings() -> Settings:
    """Returns a cached singleton instance of application settings."""
    return Settings()
