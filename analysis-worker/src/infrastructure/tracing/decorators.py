from functools import wraps
from opentelemetry import trace


def traced(span_name: str):
    def decorator(fn):
        @wraps(fn)
        async def wrapper(self, change):
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
