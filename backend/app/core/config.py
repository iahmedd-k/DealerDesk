from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr, field_validator
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
    vehicle_images_bucket_id: str = Field(
        default="vehicle-images",
        validation_alias=AliasChoices(
            "VEHICLE_IMAGES_BUCKET_ID",
            "vehicle_images_bucket_id",
        ),
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
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"],
        validation_alias=AliasChoices("CORS_ORIGINS", "cors_origins"),
    )
    auth_rate_limit: str = Field(
        default="10/minute",
        validation_alias=AliasChoices("AUTH_RATE_LIMIT", "auth_rate_limit"),
    )
    embedding_api_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("EMBEDDING_API_URL", "embedding_api_url"),
    )
    embedding_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "EMBEDDING_API_KEY",
            "embedding_api_key",
        ),
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        validation_alias=AliasChoices("EMBEDDING_MODEL", "embedding_model"),
    )
    llm_api_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_API_URL", "llm_api_url"),
    )
    llm_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_API_KEY", "llm_api_key"),
    )
    llm_model: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("LLM_MODEL", "llm_model"),
    )
    llm_provider: str = Field(
        default="auto",
        validation_alias=AliasChoices("LLM_PROVIDER", "llm_provider"),
    )
    dealerdesk_admin_name: str = Field(
        default="DealerDesk Admin",
        validation_alias=AliasChoices(
            "DEALERDESK_ADMIN_NAME",
            "dealerdesk_admin_name",
        ),
    )
    dealerdesk_admin_email: str = Field(
        default="dealerdesk@demo.com",
        validation_alias=AliasChoices(
            "DEALERDESK_ADMIN_EMAIL",
            "dealerdesk_admin_email",
        ),
    )
    dealerdesk_admin_password: SecretStr = Field(
        default=SecretStr("adminadmin"),
        validation_alias=AliasChoices(
            "DEALERDESK_ADMIN_PASSWORD",
            "dealerdesk_admin_password",
        ),
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

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
