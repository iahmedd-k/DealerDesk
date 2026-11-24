import logging
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import engine
from app.repositories.health_repository import check_database

logger = logging.getLogger(__name__)


def get_health_report(db: Session) -> tuple[dict[str, Any], bool]:
    settings = get_settings()
    db_status = "connected"
    db_latency_ms: float | None = None
    start = time.perf_counter()
    try:
        check_database(db)
        db_latency_ms = round((time.perf_counter() - start) * 1000, 2)
    except SQLAlchemyError:
        logger.exception("Database health check failed")
        db_status = "unavailable"

    pool_metrics = None
    try:
        pool = engine.pool
        pool_metrics = {
            "size": pool.size(),
            "checkedin": pool.checkedin(),
            "checkedout": pool.checkedout(),
            "overflow": pool.overflow(),
        }
    except Exception as exc:
        logger.debug("Could not read pool stats: %s", exc)

    healthy = db_status == "connected"
    return (
        {
            "status": "healthy" if healthy else "unhealthy",
            "environment": getattr(settings, "environment", "development"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": {
                "status": db_status,
                "latency_ms": db_latency_ms,
                "pool": pool_metrics,
            },
            "services": {
                "storage": (
                    "configured"
                    if settings.supabase_url and settings.supabase_key
                    else "unconfigured"
                ),
                "email": "configured" if settings.resend_api_key else "unconfigured",
                "embeddings": (
                    "remote" if settings.embedding_api_url else "local_deterministic"
                ),
                "llm": (
                    "remote"
                    if settings.llm_api_url and settings.llm_api_key
                    else "local_deterministic"
                ),
            },
        },
        healthy,
    )
