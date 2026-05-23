from collections.abc import Callable
from functools import wraps
from typing import Any

from opentelemetry import trace


def traced(span_name: str) -> Callable[..., Any]:
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        async def wrapper(self: Any, result: Any) -> Any:
            with trace.get_tracer(__name__).start_as_current_span(
                span_name,
                attributes={"repository": result.repository, "sha": result.sha},
            ):
                return await fn(self, result)

        return wrapper

    return decorator
