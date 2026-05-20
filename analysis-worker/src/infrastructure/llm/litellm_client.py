import structlog
from litellm import acompletion
from litellm import (
    APIConnectionError,
    BadGatewayError,
    InternalServerError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.domain.ports.llm_client import LLMClient
from src.infrastructure.llm.analyzer_config import (
    CB_FAILURE_THRESHOLD,
    CB_RESET_TIMEOUT,
    LLM_MAX_ATTEMPTS,
    LLM_TIMEOUT,
    LLM_WAIT_MAX,
    LLM_WAIT_MIN,
    LLM_WAIT_MULTIPLIER,
)
from src.infrastructure.llm.circuit_breaker import circuit_breaker

logger = structlog.get_logger()

_LLM_RETRYABLE = (
    RateLimitError,
    ServiceUnavailableError,
    APIConnectionError,
    InternalServerError,
    BadGatewayError,
    Timeout,
)


class LiteLLMClient(LLMClient):
    def __init__(self, model: str, api_key: str):
        self._model = model
        self._api_key = api_key

    @circuit_breaker(failure_threshold=CB_FAILURE_THRESHOLD, reset_timeout=CB_RESET_TIMEOUT)
    @retry(
        stop=stop_after_attempt(LLM_MAX_ATTEMPTS),
        wait=wait_exponential(
            multiplier=LLM_WAIT_MULTIPLIER, min=LLM_WAIT_MIN, max=LLM_WAIT_MAX
        ),
        retry=retry_if_exception_type(_LLM_RETRYABLE),
        reraise=True,
        before_sleep=lambda rs: logger.warning(
            "llm_retry", attempt=rs.attempt_number, error=str(rs.outcome.exception())
        ),
    )
    async def call(self, prompt: str) -> str:
        response = await acompletion(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            api_key=self._api_key,
            timeout=LLM_TIMEOUT,
        )
        content = response.choices[0].message.content
        logger.debug("llm_raw_response", chars=len(content or ""), preview=(content or "")[:300])
        return content
