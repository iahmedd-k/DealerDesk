from typing import Any

from app.core.config import get_settings


def get_supabase_client() -> Any:
    from supabase import create_client

    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be configured")
    return create_client(settings.supabase_url, settings.supabase_key.get_secret_value())
