from functools import wraps
from opentelemetry import trace


def traced(span_name: str):
    def decorator(fn):
        @wraps(fn)
        async def wrapper(self, result):
            with trace.get_tracer(__name__).start_as_current_span(
                span_name,
                attributes={"repository": result.repository, "sha": result.sha},
            ):
                return await fn(self, result)

        return wrapper

    return decorator
