import structlog
from langfuse import Langfuse
from opentelemetry import trace

from src.domain.ports.prompt_repository import PromptRepository

logger = structlog.get_logger()


class LangfusePromptRepository(PromptRepository):
    def __init__(self, client: Langfuse, prompt_name: str, cache_ttl_seconds: int = 60):
        self._client = client
        self._prompt_name = prompt_name
        self._cache_ttl = cache_ttl_seconds

    def compile(self, variables: dict[str, str]) -> str:
        template = self._client.get_prompt(
            self._prompt_name, cache_ttl_seconds=self._cache_ttl
        )
        span = trace.get_current_span()
        if span.is_recording():
            span.set_attribute("prompt_version", str(template.version))

        if template.is_fallback:
            logger.warning(
                "prompt_fallback",
                prompt_name=self._prompt_name,
                reason="langfuse_unreachable",
            )
        logger.debug(
            "prompt_fetched",
            prompt_name=self._prompt_name,
            prompt_version=template.version,
            prompt_labels=template.labels,
            prompt_commit=template.commit_message,
        )
        return template.compile(**variables)
