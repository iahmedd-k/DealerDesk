import json
import logging
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import get_settings

logger = logging.getLogger("dealerdesk.redis")


class UpstashRedisClient:
    """Lightweight, fault-tolerant Upstash Redis REST client using httpx."""

    def __init__(self) -> None:
        self._client = httpx.Client(timeout=2.5)

    def _creds(self) -> tuple[str, str] | None:
        settings = get_settings()
        url = (settings.upstash_redis_rest_url or "").strip().rstrip("/")
        token = (
            settings.upstash_redis_rest_token.get_secret_value().strip()
            if settings.upstash_redis_rest_token
            else ""
        )
        if not url or not token:
            return None
        return url, token

    @property
    def is_configured(self) -> bool:
        return self._creds() is not None

    def _headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def ping(self) -> bool:
        creds = self._creds()
        if not creds:
            return False
        url, token = creds
        try:
            resp = self._client.get(f"{url}/ping", headers=self._headers(token))
            return resp.status_code == 200 and resp.json().get("result") == "PONG"
        except Exception as exc:
            logger.warning("Upstash Redis ping failed: %s", exc)
            return False

    def get_json(self, key: str) -> Any | None:
        creds = self._creds()
        if not creds:
            return None
        url, token = creds
        try:
            resp = self._client.get(
                f"{url}/get/{quote(key, safe='')}",
                headers=self._headers(token),
            )
            if resp.status_code != 200:
                return None
            raw = resp.json().get("result")
            if raw is None:
                return None
            return json.loads(raw) if isinstance(raw, str) else raw
        except Exception as exc:
            logger.debug("Redis get_json failed for %s: %s", key, exc)
            return None

    def set_json(self, key: str, value: Any, ttl_seconds: int = 60) -> bool:
        creds = self._creds()
        if not creds:
            return False
        url, token = creds
        try:
            payload = ["SET", key, json.dumps(value, default=str), "EX", int(ttl_seconds)]
            resp = self._client.post(
                url,
                headers=self._headers(token),
                json=payload,
            )
            return resp.status_code == 200
        except Exception as exc:
            logger.debug("Redis set_json failed for %s: %s", key, exc)
            return False

    def delete(self, *keys: str) -> None:
        creds = self._creds()
        if not creds or not keys:
            return
        url, token = creds
        try:
            self._client.post(
                url,
                headers=self._headers(token),
                json=["DEL", *keys],
            )
        except Exception as exc:
            logger.debug("Redis delete failed for %s: %s", keys, exc)

    def incr_window(self, key: str, window_seconds: int) -> int | None:
        """Atomically increments a rate-limit counter and sets NX expiry."""
        creds = self._creds()
        if not creds:
            return None
        url, token = creds
        try:
            resp = self._client.post(
                f"{url}/pipeline",
                headers=self._headers(token),
                json=[
                    ["INCR", key],
                    ["EXPIRE", key, int(window_seconds), "NX"],
                ],
            )
            if resp.status_code != 200:
                return None
            results = resp.json()
            if isinstance(results, list) and results:
                return int(results[0].get("result", 0))
            return None
        except Exception as exc:
            logger.debug("Redis incr_window failed for %s: %s", key, exc)
            return None


redis_client = UpstashRedisClient()
