import asyncio
import time
import structlog
from enum import Enum
from functools import wraps

logger = structlog.get_logger()


class CircuitBreakerOpenError(Exception):
    pass


class _State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class _CircuitBreakerState:
    def __init__(self, failure_threshold: int, reset_timeout: float):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.state = _State.CLOSED
        self.failure_count = 0
        self.last_failure_time: float = 0.0
        self.lock = asyncio.Lock()

    async def check(self) -> None:
        async with self.lock:
            if self.state == _State.OPEN:
                if time.monotonic() - self.last_failure_time >= self.reset_timeout:
                    self.state = _State.HALF_OPEN
                    logger.info("circuit_breaker_half_open")
                else:
                    raise CircuitBreakerOpenError()

    async def on_success(self) -> None:
        async with self.lock:
            if self.state in (_State.HALF_OPEN, _State.OPEN):
                logger.info("circuit_breaker_closed")
            self.state = _State.CLOSED
            self.failure_count = 0

    async def on_failure(self) -> None:
        async with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.monotonic()
            if (
                self.failure_count >= self.failure_threshold
                and self.state != _State.OPEN
            ):
                logger.warning("circuit_breaker_open", failures=self.failure_count)
                self.state = _State.OPEN


def circuit_breaker(failure_threshold: int, reset_timeout: float):
    def decorator(fn):
        state_attr = f"_cb_{fn.__name__}"

        @wraps(fn)
        async def wrapper(self, *args, **kwargs):
            if not hasattr(self, state_attr):
                setattr(
                    self,
                    state_attr,
                    _CircuitBreakerState(failure_threshold, reset_timeout),
                )
            state: _CircuitBreakerState = getattr(self, state_attr)
            await state.check()
            try:
                result = await fn(self, *args, **kwargs)
                await state.on_success()
                return result
            except Exception:
                await state.on_failure()
                raise

        return wrapper

    return decorator
