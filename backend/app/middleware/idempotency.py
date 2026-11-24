import asyncio
import base64
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.db.session import SessionLocal
from app.models.idempotency import IdempotencyKey

logger = logging.getLogger(__name__)

IDEMPOTENCY_TTL_SECONDS = 86400
LOCK_LEASE_SECONDS = 30
MAX_CACHED_RESPONSE_BYTES = 1024 * 1024
MAX_IDEMPOTENT_REQUEST_BYTES = 20 * 1024 * 1024


class IdempotencyMiddleware:
    """
    Distributed, database-backed idempotency middleware.
    Protects mutating operations (POST, PUT, PATCH, DELETE) against concurrent duplicate executions
    and replays responses for retried requests across multiple workers and service restarts.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._local_locks: dict[str, asyncio.Lock] = {}
        self._memory_fallback: dict[str, dict[str, Any]] = {}

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

        # In-process lock to prevent duplicate async coroutine tasks in the same worker process
        if scope_key not in self._local_locks:
            self._local_locks[scope_key] = asyncio.Lock()
        local_lock = self._local_locks[scope_key]

        await local_lock.acquire()
        try:
            # Query/acquire database idempotency lease
            lease_action, cached_response, error_msg = await asyncio.to_thread(
                self._check_or_acquire_lease, scope_key, request_hash
            )

            if lease_action == "conflict":
                await self._send_error(
                    send,
                    409,
                    error_msg or "Conflict with idempotency key",
                )
                return

            if lease_action == "replayed" and cached_response is not None:
                replay_headers = [
                    (header[0].encode("latin-1"), header[1].encode("latin-1"))
                    for header in cached_response.get("headers", [])
                ] + [(b"idempotent-replayed", b"true")]
                replay_body = (
                    base64.b64decode(cached_response["body"].encode("ascii"))
                    if cached_response.get("body")
                    else b""
                )
                await send(
                    {
                        "type": "http.response.start",
                        "status": cached_response.get("status", 200),
                        "headers": replay_headers,
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": replay_body,
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
                    if not message.get("more_body", False):
                        if (
                            response_cacheable
                            and response_status is not None
                            and 200 <= response_status < 300
                        ):
                            await asyncio.to_thread(
                                self._complete_lease,
                                scope_key,
                                response_status,
                                response_headers,
                                bytes(response_body),
                                request_hash,
                            )
                        else:
                            await asyncio.to_thread(
                                self._fail_lease,
                                scope_key,
                            )
                await send(message)

            try:
                await self.app(
                    scope,
                    self._replay_receive(receive, request_body),
                    capture_send,
                )
            except Exception:
                await asyncio.to_thread(self._fail_lease, scope_key)
                raise
        finally:
            local_lock.release()
            if not local_lock.locked() and scope_key in self._local_locks:
                self._local_locks.pop(scope_key, None)

    def _check_or_acquire_lease(
        self, scope_key: str, request_hash: str
    ) -> tuple[str, dict[str, Any] | None, str | None]:
        now = datetime.now(timezone.utc)
        db = SessionLocal()
        try:
            record = (
                db.query(IdempotencyKey)
                .filter(IdempotencyKey.scope_key == scope_key)
                .first()
            )
            if record is not None:
                # Handle expired keys
                record_expires = (
                    record.expires_at.replace(tzinfo=timezone.utc)
                    if record.expires_at.tzinfo is None
                    else record.expires_at
                )
                if record_expires <= now:
                    record.request_hash = request_hash
                    record.status = "in_progress"
                    record.locked_until = now + timedelta(seconds=LOCK_LEASE_SECONDS)
                    record.expires_at = now + timedelta(seconds=IDEMPOTENCY_TTL_SECONDS)
                    record.status_code = None
                    record.headers = None
                    record.response_body = None
                    db.commit()
                    return ("acquired", None, None)

                if record.status == "completed":
                    if record.request_hash != request_hash:
                        return (
                            "conflict",
                            None,
                            "This idempotency key was already used with a different request",
                        )
                    return (
                        "replayed",
                        {
                            "status": record.status_code or 200,
                            "headers": record.headers or [],
                            "body": record.response_body or "",
                        },
                        None,
                    )

                if record.status == "in_progress":
                    record_locked = (
                        record.locked_until.replace(tzinfo=timezone.utc)
                        if record.locked_until.tzinfo is None
                        else record.locked_until
                    )
                    if record_locked > now:
                        return (
                            "conflict",
                            None,
                            "Request is currently being processed by another worker",
                        )
                    # Lease expired on abandoned request, take over lock lease
                    record.request_hash = request_hash
                    record.status = "in_progress"
                    record.locked_until = now + timedelta(seconds=LOCK_LEASE_SECONDS)
                    db.commit()
                    return ("acquired", None, None)

                # Previous attempt failed, allow retry
                record.request_hash = request_hash
                record.status = "in_progress"
                record.locked_until = now + timedelta(seconds=LOCK_LEASE_SECONDS)
                db.commit()
                return ("acquired", None, None)

            # Record does not exist, insert initial record
            new_record = IdempotencyKey(
                scope_key=scope_key,
                request_hash=request_hash,
                status="in_progress",
                created_at=now,
                locked_until=now + timedelta(seconds=LOCK_LEASE_SECONDS),
                expires_at=now + timedelta(seconds=IDEMPOTENCY_TTL_SECONDS),
            )
            db.add(new_record)
            try:
                db.commit()
                return ("acquired", None, None)
            except IntegrityError:
                db.rollback()
                # Concurrent race condition: re-query
                return self._check_or_acquire_lease(
                    scope_key, request_hash
                )
        except SQLAlchemyError as exc:
            logger.warning("Database error during idempotency check: %s", exc)
            cached = self._memory_fallback.get(scope_key)
            if cached is not None:
                if cached.get("request_hash") != request_hash:
                    return (
                        "conflict",
                        None,
                        "This idempotency key was already used with a different request",
                    )
                return ("replayed", cached, None)
            return ("acquired", None, None)
        finally:
            db.close()

    def _complete_lease(
        self,
        scope_key: str,
        status_code: int,
        headers: list[tuple[bytes, bytes]],
        body: bytes,
        request_hash: str = "",
    ) -> None:
        db = SessionLocal()
        try:
            record = (
                db.query(IdempotencyKey)
                .filter(IdempotencyKey.scope_key == scope_key)
                .first()
            )
            if record is not None:
                record.status = "completed"
                record.status_code = status_code
                record.headers = [
                    [h[0].decode("latin-1"), h[1].decode("latin-1")] for h in headers
                ]
                record.response_body = base64.b64encode(body).decode("ascii")
                db.commit()
        except SQLAlchemyError as exc:
            logger.warning("Failed to save completed idempotency record: %s", exc)
            db.rollback()
            self._memory_fallback[scope_key] = {
                "status": status_code,
                "headers": [
                    [h[0].decode("latin-1"), h[1].decode("latin-1")] for h in headers
                ],
                "body": base64.b64encode(body).decode("ascii"),
                "request_hash": request_hash,
            }
        finally:
            db.close()

    @staticmethod
    def _fail_lease(scope_key: str) -> None:
        db = SessionLocal()
        try:
            record = (
                db.query(IdempotencyKey)
                .filter(IdempotencyKey.scope_key == scope_key)
                .first()
            )
            if record is not None and record.status == "in_progress":
                record.status = "failed"
                db.commit()
        except SQLAlchemyError as exc:
            logger.warning("Failed to mark idempotency record as failed: %s", exc)
            db.rollback()
        finally:
            db.close()

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
