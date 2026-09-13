from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    database_url: str = 'postgresql+psycopg://portal:portal@localhost:5432/portal'
    jwt_secret: str = Field(min_length=32)
    frontend_url: str = 'http://localhost:5173'
    auth_rate_limit: int = 30


@lru_cache
def get_settings():
    return Settings()
