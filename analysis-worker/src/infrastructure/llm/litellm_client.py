import time

import litellm
import structlog
from litellm import (  # type: ignore[attr-defined]
    APIConnectionError,
    BadGatewayError,
    InternalServerError,
    ServiceUnavailableError,
    Timeout,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.domain.entities import LLMResponse
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
from src.infrastructure.llm.router_factory import build_router
from src.infrastructure.metrics import (
    llm_call_duration,
    llm_completion_tokens,
    llm_cost_usd,
    llm_prompt_tokens,
)
from src.infrastructure.retry_logging import make_retry_logger

logger = structlog.get_logger()


_LLM_RETRYABLE = (
    ServiceUnavailableError,
    APIConnectionError,
    InternalServerError,
    BadGatewayError,
    Timeout,
)


class LiteLLMClient(LLMClient):
    def __init__(self, configs: list[tuple[str, str]]):
        self._model = configs[0][0]
        self._router = build_router(configs, timeout=LLM_TIMEOUT)

    @circuit_breaker(
        failure_threshold=CB_FAILURE_THRESHOLD, reset_timeout=CB_RESET_TIMEOUT
    )
    @retry(
        stop=stop_after_attempt(LLM_MAX_ATTEMPTS),
        wait=wait_exponential(
            multiplier=LLM_WAIT_MULTIPLIER, min=LLM_WAIT_MIN, max=LLM_WAIT_MAX
        ),
        retry=retry_if_exception_type(_LLM_RETRYABLE),
        reraise=True,
        before_sleep=make_retry_logger("llm_retry"),
    )
    async def call(self, prompt: str) -> LLMResponse:
        start = time.perf_counter()
        response = await self._router.acompletion(
            model="config-0",
            messages=[{"role": "user", "content": prompt}],
        )
        latency = time.perf_counter() - start
        content: str = response.choices[0].message.content or ""
        usage = response.usage  # type: ignore[attr-defined]
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        try:
            cost = litellm.completion_cost(completion_response=response) or 0.0
        except Exception:
            cost = 0.0
        llm_response = LLMResponse(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_seconds=latency,
            cost_usd=cost,
        )
        self._observe(llm_response)
        return llm_response

    def _observe(self, response: LLMResponse) -> None:
        attrs = {"model": self._model}
        llm_call_duration.record(response.latency_seconds, attrs)
        llm_prompt_tokens.add(response.prompt_tokens, attrs)
        llm_completion_tokens.add(response.completion_tokens, attrs)
        llm_cost_usd.add(response.cost_usd, attrs)
        logger.debug(
            "llm_raw_response",
            chars=len(response.content or ""),
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            latency_seconds=round(response.latency_seconds, 3),
            cost_usd=response.cost_usd,
        )
