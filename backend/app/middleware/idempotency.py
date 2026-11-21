import json
import time
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

# In-memory LRU cache for idempotent requests with TTL (24 hours)
IDEMPOTENCY_TTL_SECONDS = 86400
_idempotency_cache: dict[str, tuple[float, int, dict[str, str], bytes]] = {}


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        idempotency_key = request.headers.get("Idempotency-Key")

        # Idempotency only applies to state-changing requests when the header is provided
        if not idempotency_key or request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return await call_next(request)

        idempotency_key = idempotency_key.strip()
        if len(idempotency_key) > 128:
            return StarletteResponse(
                content=json.dumps({"detail": "Idempotency-Key header must be 128 characters or fewer"}),
                status_code=400,
                media_type="application/json",
            )

        now = time.time()
        # Clean expired keys periodically
        if len(_idempotency_cache) > 2000:
            expired = [k for k, (exp, _, _, _) in _idempotency_cache.items() if exp < now]
            for k in expired:
                _idempotency_cache.pop(k, None)

        cached = _idempotency_cache.get(idempotency_key)
        if cached:
            expiry, status_code, headers, body = cached
            if expiry > now:
                res_headers = dict(headers)
                res_headers["Idempotent-Replayed"] = "true"
                return StarletteResponse(
                    content=body,
                    status_code=status_code,
                    headers=res_headers,
                    media_type=res_headers.get("content-type", "application/json"),
                )

        response = await call_next(request)

        # Cache only successful / client error responses (do not cache transient 5xx server errors)
        if response.status_code < 500:
            body = [chunk async for chunk in response.body_iterator]
            response_body = b"".join(body)

            cache_headers = {
                k: v for k, v in response.headers.items()
                if k.lower() in {"content-type", "content-language", "etag"}
            }
            _idempotency_cache[idempotency_key] = (
                now + IDEMPOTENCY_TTL_SECONDS,
                response.status_code,
                cache_headers,
                response_body,
            )

            return StarletteResponse(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        return response
