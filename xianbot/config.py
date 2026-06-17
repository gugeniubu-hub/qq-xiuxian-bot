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
    sign_in_base_min: int = Field(default=120)
    sign_in_base_max: int = Field(default=180)
    sign_in_cultivation_min: int = Field(default=40)
    sign_in_cultivation_max: int = Field(default=80)
    meditation_default_minutes: int = Field(default=30)
    meditation_min_minutes: int = Field(default=10)
    meditation_max_minutes: int = Field(default=180)
    adventure_stamina_cost: int = Field(default=20)
    breakthrough_max_item_loss_rate: float = Field(default=0.18)
    breakthrough_fail_penalty_rate: float = Field(default=0.22)


@lru_cache
def get_settings() -> Settings:
    return Settings()
