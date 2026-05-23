from collections.abc import Callable
from functools import wraps
from typing import Any

from opentelemetry import trace


def traced(span_name: str) -> Callable[..., Any]:
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        async def wrapper(self: Any, change: Any) -> Any:
            with trace.get_tracer(__name__).start_as_current_span(
                span_name,
                attributes={
                    "repository": change.repository,
                    "sha": change.target_sha,
                },
            ):
                return await fn(self, change)

        return wrapper

    return decorator
