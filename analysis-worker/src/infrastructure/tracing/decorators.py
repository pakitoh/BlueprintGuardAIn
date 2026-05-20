from functools import wraps
from opentelemetry import trace

from src.application.services.prompt_config import PROMPT_VERSION


def traced(span_name: str):
    def decorator(fn):
        @wraps(fn)
        async def wrapper(self, change):
            with trace.get_tracer(__name__).start_as_current_span(
                span_name,
                attributes={
                    "repository": change.repository,
                    "sha": change.target_sha,
                    "prompt_version": PROMPT_VERSION,
                },
            ):
                return await fn(self, change)

        return wrapper

    return decorator
