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
    adventure_stamina_cost: int = Field(default=12)
    breakthrough_max_item_loss_rate: float = Field(default=0.18)
    breakthrough_fail_penalty_rate: float = Field(default=0.22)
    lifespan_progress_per_adventure: int = Field(default=2)
    lifespan_progress_per_encounter: int = Field(default=1)
    lifespan_progress_per_60_meditation_minutes: int = Field(default=1)
    method_mastery_meditation_gain: int = Field(default=3)
    method_mastery_adventure_gain: int = Field(default=2)
    method_mastery_encounter_gain: int = Field(default=4)
    stamina_recover_interval_seconds: int = Field(default=300)
    stamina_recover_amount: int = Field(default=2)
    duel_stamina_cost: int = Field(default=10)
    duel_daily_reward_spirit_stones_min: int = Field(default=28)
    duel_daily_reward_spirit_stones_max: int = Field(default=66)
    sqlite_journal_mode: str = Field(default="WAL")
    sqlite_synchronous: str = Field(default="NORMAL")
    sqlite_busy_timeout_ms: int = Field(default=30000)
    sqlite_cache_size_kb: int = Field(default=8192)
    sqlite_mmap_size_mb: int = Field(default=128)
    sqlite_wal_autocheckpoint: int = Field(default=1000)
    sqlite_journal_size_limit_mb: int = Field(default=64)
    sqlite_temp_store: str = Field(default="MEMORY")
    maintenance_interval_seconds: int = Field(default=3600)
    cleanup_action_log_days: int = Field(default=30)
    cleanup_action_log_keep_latest_per_user: int = Field(default=200)
    cleanup_signin_days: int = Field(default=60)
    cleanup_sold_market_days: int = Field(default=30)
    cleanup_world_days: int = Field(default=45)
    cleanup_cooldown_grace_days: int = Field(default=3)
    cleanup_rebirth_log_days: int = Field(default=365)
    action_cooldown_adventure_seconds: int = Field(default=0)
    action_cooldown_encounter_seconds: int = Field(default=0)
    action_cooldown_duel_seconds: int = Field(default=0)
    action_cooldown_trial_seconds: int = Field(default=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
