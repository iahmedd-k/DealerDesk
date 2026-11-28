from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    environment: str = Field(
        default="development",
        validation_alias=AliasChoices("ENVIRONMENT", "environment"),
    )
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
        default=300,
        ge=-1,
        validation_alias=AliasChoices("DATABASE_POOL_RECYCLE", "database_pool_recycle"),
    )
    database_pool_pre_ping: bool = Field(
        default=False,
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
    google_oauth_client_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_OAUTH_CLIENT_ID", "google_oauth_client_id"),
    )
    google_oauth_client_secret: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "GOOGLE_OAUTH_CLIENT_SECRET",
            "google_oauth_client_secret",
        ),
    )
    google_oauth_redirect_uri: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "GOOGLE_OAUTH_REDIRECT_URI",
            "google_oauth_redirect_uri",
        ),
    )
    gmail_token_encryption_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "GMAIL_TOKEN_ENCRYPTION_KEY",
            "gmail_token_encryption_key",
        ),
    )
    frontend_base_url: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("FRONTEND_BASE_URL", "frontend_base_url"),
    )
    twilio_account_sid: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("TWILIO_ACCOUNT_SID", "twilio_account_sid"),
    )
    twilio_auth_token: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("TWILIO_AUTH_TOKEN", "twilio_auth_token"),
    )
    twilio_whatsapp_from: str = Field(
        default="whatsapp:+14155238886",
        validation_alias=AliasChoices("TWILIO_WHATSAPP_FROM", "twilio_whatsapp_from"),
    )
    twilio_webhook_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "TWILIO_WEBHOOK_BASE_URL",
            "twilio_webhook_base_url",
        ),
    )
    twilio_status_callback_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "TWILIO_STATUS_CALLBACK_URL",
            "twilio_status_callback_url",
        ),
    )
    vapi_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("VAPI_API_KEY", "vapi_api_key"),
    )
    vapi_assistant_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VAPI_ASSISTANT_ID", "vapi_assistant_id"),
    )
    vapi_phone_number_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VAPI_PHONE_NUMBER_ID", "vapi_phone_number_id"),
    )
    vapi_webhook_secret: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("VAPI_WEBHOOK_SECRET", "vapi_webhook_secret"),
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ],
        validation_alias=AliasChoices("CORS_ORIGINS", "cors_origins"),
    )
    cors_origin_regex: str | None = Field(
        default=(
            r"^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
            r"192\.168\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(:\d+)?$"
        ),
        validation_alias=AliasChoices("CORS_ORIGIN_REGEX", "cors_origin_regex"),
    )
    auth_rate_limit: str = Field(
        default="10/minute",
        validation_alias=AliasChoices("AUTH_RATE_LIMIT", "auth_rate_limit"),
    )
    assistant_rate_limit: str = Field(
        default="20/minute",
        validation_alias=AliasChoices("ASSISTANT_RATE_LIMIT", "assistant_rate_limit"),
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
    groq_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("GROQ_API_KEY", "groq_api_key"),
    )
    groq_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GROQ_BASE_URL", "groq_base_url"),
    )
    groq_model: str = Field(
        default="llama-3.3-70b-versatile",
        validation_alias=AliasChoices("GROQ_MODEL", "groq_model"),
    )
    groq_fallback_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GROQ_FALLBACK_MODEL", "groq_fallback_model"),
    )

    def get_llm_config(self) -> tuple[str, str, str, str | None] | None:
        """Return (chat_completions_url, api_key, model, fallback_model) if an LLM is configured."""
        if self.llm_api_url and self.llm_api_key and self.llm_api_key.get_secret_value():
            url = self.llm_api_url.rstrip("/")
            if not url.endswith("/chat/completions"):
                url = f"{url}/chat/completions"
            return url, self.llm_api_key.get_secret_value(), self.llm_model, None
        if self.groq_api_key and self.groq_api_key.get_secret_value():
            base = (self.groq_base_url or "https://api.groq.com/openai/v1").rstrip("/")
            url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
            return url, self.groq_api_key.get_secret_value(), self.groq_model, self.groq_fallback_model
        return None
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
    upstash_redis_rest_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "UPSTASH_REDIS_REST_URL",
            "upstash_redis_rest_url",
        ),
    )
    upstash_redis_rest_token: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "UPSTASH_REDIS_REST_TOKEN",
            "upstash_redis_rest_token",
        ),
    )
    redis_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("REDIS_URL", "redis_url"),
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.environment.lower() == "production":
            if (
                not self.jwt_secret_key
                or len(self.jwt_secret_key.get_secret_value()) < 32
            ):
                raise ValueError(
                    "In production, JWT_SECRET_KEY must be configured with at least 32 characters"
                )
            insecure_keys = {
                "test-only-jwt-secret-that-is-at-least-32-bytes",
                "default_secret_key_change_in_production",
                "supersecretkeychangeinproduction12345",
            }
            if self.jwt_secret_key.get_secret_value() in insecure_keys:
                raise ValueError(
                    "In production, JWT_SECRET_KEY cannot be a known default test key"
                )

            if "*" in self.cors_origins:
                raise ValueError(
                    "In production with allow_credentials=True, CORS_ORIGINS cannot contain '*'"
                )

            if self.supabase_url and not self.supabase_key:
                raise ValueError(
                    "In production, SUPABASE_KEY must be provided if SUPABASE_URL is set"
                )

            admin_pw = self.dealerdesk_admin_password.get_secret_value().strip()
            if admin_pw == "adminadmin" or len(admin_pw) < 12:
                raise ValueError(
                    "In production, DEALERDESK_ADMIN_PASSWORD cannot be 'adminadmin' and must be at least 12 characters"
                )

        return self

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

    # Production safety validations
    if settings.environment.lower() == "production":
        if (
            not settings.jwt_secret_key
            or len(settings.jwt_secret_key.get_secret_value()) < 32
        ):
            raise ValueError(
                "In production, JWT_SECRET_KEY must be configured with at least 32 characters"
            )
        insecure_keys = {
            "test-only-jwt-secret-that-is-at-least-32-bytes",
            "default_secret_key_change_in_production",
            "supersecretkeychangeinproduction12345",
        }
        if settings.jwt_secret_key.get_secret_value() in insecure_keys:
            raise ValueError(
                "In production, JWT_SECRET_KEY cannot be a known default test key"
            )

        if "*" in settings.cors_origins:
            raise ValueError(
                "In production with allow_credentials=True, CORS_ORIGINS cannot contain '*'"
            )

        if settings.supabase_url and not settings.supabase_key:
            raise ValueError(
                "In production, SUPABASE_KEY must be provided if SUPABASE_URL is set"
            )

    return settings
