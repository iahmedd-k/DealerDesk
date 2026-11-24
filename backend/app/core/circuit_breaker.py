from collections.abc import Callable
from datetime import datetime, timezone
from enum import Enum
import logging
import threading
from typing import Any, TypeVar

logger = logging.getLogger("dealerdesk.circuit_breaker")

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"          # Normal operation; requests pass through
    OPEN = "open"              # Failures exceeded threshold; fast fail immediately
    HALF_OPEN = "half_open"    # Recovery probe period; testing with limited calls


class CircuitBreakerOpenError(Exception):
    """Raised when an operation is attempted while the circuit breaker is OPEN."""

    def __init__(self, service_name: str, retry_after_seconds: float) -> None:
        super().__init__(
            f"Service '{service_name}' is temporarily unavailable (circuit open). "
            f"Retry after {retry_after_seconds:.1f}s."
        )
        self.service_name = service_name
        self.retry_after_seconds = retry_after_seconds


class CircuitBreaker:
    """
    Thread-safe and async-safe Circuit Breaker pattern implementation.
    Prevents cascading failures by short-circuiting downstream calls to
    failing external services (e.g. LLM APIs, WhatsApp Cloud API, Telephony).
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 30.0,
        expected_exceptions: tuple[type[Exception], ...] = (Exception,),
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.expected_exceptions = expected_exceptions

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_state_change: datetime = datetime.now(timezone.utc)
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._check_state_transition()
            return self._state

    def _check_state_transition(self) -> None:
        now = datetime.now(timezone.utc)
        if self._state == CircuitState.OPEN:
            elapsed = (now - self._last_state_change).total_seconds()
            if elapsed >= self.recovery_timeout_seconds:
                logger.info(
                    "Circuit breaker '%s' entering HALF_OPEN probe state after %.1fs",
                    self.name,
                    elapsed,
                )
                self._state = CircuitState.HALF_OPEN
                self._last_state_change = now

    def record_success(self) -> None:
        with self._lock:
            if self._state != CircuitState.CLOSED:
                logger.info(
                    "Circuit breaker '%s' recovered from %s to CLOSED",
                    self.name,
                    self._state.value,
                )
            self._failure_count = 0
            self._state = CircuitState.CLOSED
            self._last_state_change = datetime.now(timezone.utc)

    def record_failure(self, exc: Exception) -> None:
        with self._lock:
            self._failure_count += 1
            now = datetime.now(timezone.utc)
            logger.warning(
                "Circuit breaker '%s' recorded failure #%d: %s",
                self.name,
                self._failure_count,
                exc,
            )
            if self._state == CircuitState.HALF_OPEN or self._failure_count >= self.failure_threshold:
                if self._state != CircuitState.OPEN:
                    logger.error(
                        "Circuit breaker '%s' TRIPPED to OPEN state. Threshold=%d reached.",
                        self.name,
                        self.failure_threshold,
                    )
                self._state = CircuitState.OPEN
                self._last_state_change = now

    def check_permission(self) -> None:
        with self._lock:
            self._check_state_transition()
            if self._state == CircuitState.OPEN:
                now = datetime.now(timezone.utc)
                elapsed = (now - self._last_state_change).total_seconds()
                retry_after = max(0.0, self.recovery_timeout_seconds - elapsed)
                raise CircuitBreakerOpenError(self.name, retry_after)

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Executes a synchronous callable protected by the circuit breaker."""
        self.check_permission()
        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except self.expected_exceptions as exc:
            self.record_failure(exc)
            raise

    async def call_async(self, coro_func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Executes an asynchronous coroutine protected by the circuit breaker."""
        self.check_permission()
        try:
            result = await coro_func(*args, **kwargs)
            self.record_success()
            return result
        except self.expected_exceptions as exc:
            self.record_failure(exc)
            raise


# Pre-configured circuit breakers for external integrations
llm_circuit_breaker = CircuitBreaker("llm_provider", failure_threshold=4, recovery_timeout_seconds=20.0)
whatsapp_circuit_breaker = CircuitBreaker("whatsapp_api", failure_threshold=5, recovery_timeout_seconds=30.0)
voice_circuit_breaker = CircuitBreaker("voice_telephony", failure_threshold=3, recovery_timeout_seconds=30.0)
email_circuit_breaker = CircuitBreaker("email_service", failure_threshold=5, recovery_timeout_seconds=45.0)
