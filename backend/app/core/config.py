from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application settings
    app_name: str = "OpsFlow API"
    app_env: str = "development"
    frontend_origin: str = "http://localhost:5173"
    api_v1_prefix: str = "/api/v1"

    # Database settings
    database_url: str
    test_database_url: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]


settings = get_settings()