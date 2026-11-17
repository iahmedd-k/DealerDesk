from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    database_url: str = Field(
        validation_alias=AliasChoices(
            "SUPABASE_CONNECTION_STRING",
            "supabase_string",
            "DATABASE_URL",
        )
    )
    jwt_secret_key: SecretStr | None = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    database_pool_size: int = Field(
        default=5,
        ge=1,
        validation_alias=AliasChoices("DATABASE_POOL_SIZE", "database_pool_size"),
    )
    database_max_overflow: int = Field(
        default=10,
        ge=0,
        validation_alias=AliasChoices("DATABASE_MAX_OVERFLOW", "database_max_overflow"),
    )
    database_pool_timeout: int = Field(
        default=30,
        ge=1,
        validation_alias=AliasChoices("DATABASE_POOL_TIMEOUT", "database_pool_timeout"),
    )
    database_pool_recycle: int = Field(
        default=1800,
        ge=-1,
        validation_alias=AliasChoices("DATABASE_POOL_RECYCLE", "database_pool_recycle"),
    )
    database_pool_pre_ping: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "DATABASE_POOL_PRE_PING",
            "database_pool_pre_ping",
        ),
    )
    database_schema: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_SCHEMA", "database_schema"),
    )
    supabase_url: str | None = None
    supabase_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SUPABASE_SECRET_KEY",
            "SUPABASE_KEY",
            "SUPABASE_PUBLISHABLE_KEY",
        ),
    )
    supabase_bucket_id: str = Field(
        default="brand-logos",
        validation_alias=AliasChoices("SUPABASE_BUCKET_ID", "supabase_bucket_id"),
    )
    resend_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("resend_api_key", "RESEND_API_KEY"),
    )
    resend_from_email: str = Field(
        default="DealerDesk Support <support@ahmedkhandev.tech>",
        validation_alias=AliasChoices("RESEND_FROM_EMAIL", "resend_from_email"),
    )
    resend_reply_to: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RESEND_REPLY_TO", "resend_reply_to"),
    )

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.database_url.startswith(("postgresql://", "postgresql+")):
        raise ValueError("database_url must contain a PostgreSQL URL")
    return settings
