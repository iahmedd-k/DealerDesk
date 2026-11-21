import asyncio
import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass

from starlette.types import ASGIApp, Message, Receive, Scope, Send


IDEMPOTENCY_TTL_SECONDS = 86400
MAX_CACHE_ENTRIES = 5000
MAX_CACHED_RESPONSE_BYTES = 1024 * 1024
MAX_IDEMPOTENT_REQUEST_BYTES = 20 * 1024 * 1024


@dataclass
class CachedResponse:
    expires_at: float
    request_hash: str
    status: int
    headers: list[tuple[bytes, bytes]]
    body: bytes


@dataclass
class LockEntry:
    lock: asyncio.Lock
    users: int = 0


class IdempotencyMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.cache: OrderedDict[str, CachedResponse] = OrderedDict()
        self.locks: dict[str, LockEntry] = {}

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        key_value = headers.get(b"idempotency-key")
        method = scope.get("method", "")
        content_type = headers.get(b"content-type", b"").lower()
        content_length = headers.get(b"content-length", b"")
        if (
            not key_value
            or method not in {"POST", "PUT", "PATCH", "DELETE"}
            or content_type.startswith(b"multipart/form-data")
            or (content_length.isdigit() and int(content_length) > MAX_IDEMPOTENT_REQUEST_BYTES)
        ):
            await self.app(scope, receive, send)
            return

        key = key_value.decode("latin-1").strip()
        if not key or len(key) > 128:
            await self._send_error(send, 400, "Idempotency-Key must be 1 to 128 characters")
            return

        body = bytearray()
        request_too_large = False
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            body.extend(message.get("body", b""))
            if len(body) > MAX_IDEMPOTENT_REQUEST_BYTES:
                request_too_large = True
            if not message.get("more_body", False):
                break
        if request_too_large:
            await self.app(scope, self._replay_receive(receive, bytes(body)), send)
            return

        authorization = headers.get(b"authorization")
        client = scope.get("client")
        principal = authorization or (
            str(client[0]).encode("utf-8") if client else b"anonymous"
        )
        scope_key = hashlib.sha256(
            b"\0".join(
                [
                    method.encode("ascii"),
                    scope.get("path", "").encode("utf-8"),
                    scope.get("query_string", b""),
                    key.encode("latin-1"),
                    hashlib.sha256(principal).digest(),
                ]
            )
        ).hexdigest()
        request_hash = hashlib.sha256(
            content_type + b"\0" + bytes(body)
        ).hexdigest()

        entry = self.locks.get(scope_key)
        if entry is None:
            entry = LockEntry(asyncio.Lock())
            self.locks[scope_key] = entry
        entry.users += 1
        await entry.lock.acquire()
        try:
            self._remove_expired()
            cached = self.cache.get(scope_key)
            if cached is not None:
                if cached.request_hash != request_hash:
                    await self._send_error(
                        send,
                        409,
                        "This idempotency key was already used with a different request",
                    )
                    return
                self.cache.move_to_end(scope_key)
                await send(
                    {
                        "type": "http.response.start",
                        "status": cached.status,
                        "headers": cached.headers
                        + [(b"idempotent-replayed", b"true")],
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": cached.body,
                        "more_body": False,
                    }
                )
                return

            request_body = bytes(body)
            response_status: int | None = None
            response_headers: list[tuple[bytes, bytes]] = []
            response_body = bytearray()
            response_cacheable = True

            async def capture_send(message: Message) -> None:
                nonlocal response_status, response_headers, response_cacheable
                if message["type"] == "http.response.start":
                    response_status = message["status"]
                    response_headers = [
                        (header_name, header_value)
                        for header_name, header_value in message.get("headers", [])
                        if header_name.lower()
                        in {b"content-type", b"content-language", b"etag", b"location"}
                    ]
                elif message["type"] == "http.response.body":
                    chunk = message.get("body", b"")
                    if response_cacheable:
                        if len(response_body) + len(chunk) <= MAX_CACHED_RESPONSE_BYTES:
                            response_body.extend(chunk)
                        else:
                            response_cacheable = False
                            response_body.clear()
                    if (
                        not message.get("more_body", False)
                        and response_cacheable
                        and response_status is not None
                        and 200 <= response_status < 300
                    ):
                        self.cache[scope_key] = CachedResponse(
                            expires_at=time.monotonic() + IDEMPOTENCY_TTL_SECONDS,
                            request_hash=request_hash,
                            status=response_status,
                            headers=response_headers,
                            body=bytes(response_body),
                        )
                        self.cache.move_to_end(scope_key)
                        self._trim_cache()
                await send(message)

            await self.app(
                scope,
                self._replay_receive(receive, request_body),
                capture_send,
            )
        finally:
            entry.lock.release()
            entry.users -= 1
            if entry.users == 0 and self.locks.get(scope_key) is entry:
                del self.locks[scope_key]

    @staticmethod
    def _replay_receive(receive: Receive, body: bytes) -> Receive:
        sent_body = False

        async def replay() -> Message:
            nonlocal sent_body
            if not sent_body:
                sent_body = True
                return {
                    "type": "http.request",
                    "body": body,
                    "more_body": False,
                }
            return await receive()

        return replay

    @staticmethod
    async def _send_error(send: Send, status: int, detail: str) -> None:
        body = json.dumps({"detail": detail}).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": body,
                "more_body": False,
            }
        )

    def _remove_expired(self) -> None:
        now = time.monotonic()
        expired = [
            cache_key
            for cache_key, cached in self.cache.items()
            if cached.expires_at <= now
        ]
        for cache_key in expired:
            self.cache.pop(cache_key, None)

    def _trim_cache(self) -> None:
        while len(self.cache) > MAX_CACHE_ENTRIES:
            self.cache.popitem(last=False)
