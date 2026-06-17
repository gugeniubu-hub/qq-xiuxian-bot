from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QXIAN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(default="sqlite:///data/qxian.db")
    market_fee_rate: float = Field(default=0.05)
    daily_pool_release_rate: float = Field(default=0.2)


@lru_cache
def get_settings() -> Settings:
    return Settings()
