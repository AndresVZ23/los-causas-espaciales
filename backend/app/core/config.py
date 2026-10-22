from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Los Causas Espaciales API"
    power_api_base: str = "https://power.larc.nasa.gov/api"
    cmr_api_base: str = "https://cmr.earthdata.nasa.gov/search"
    earthdata_token: str | None = None
    cache_ttl_hours: int = 24
    cors_origins: str = "http://localhost:3100"
    cache_dir: Path = Path(__file__).resolve().parents[2] / "data" / "cache"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
