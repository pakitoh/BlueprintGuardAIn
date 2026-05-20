import pytest
from unittest.mock import MagicMock
from litellm import ServiceUnavailableError

from src.domain.entities import LLMResponse
from src.infrastructure.llm.analyzer_config import LLM_TIMEOUT
from src.infrastructure.llm.litellm_client import LiteLLMClient


def a_client():
    return LiteLLMClient(model="gemini/gemini-2.0-flash", api_key="test-key")


@pytest.mark.asyncio
async def test_call_passes_correct_model_and_prompt(mock_litellm):
    await a_client().call("my prompt")
    mock_litellm.assert_awaited_once_with(
        model="gemini/gemini-2.0-flash",
        messages=[{"role": "user", "content": "my prompt"}],
        api_key="test-key",
        timeout=LLM_TIMEOUT,
    )


@pytest.mark.asyncio
async def test_call_returns_llm_response(mock_litellm):
    mock_litellm.return_value.choices[0].message.content = "LLM finding"
    mock_litellm.return_value.usage.prompt_tokens = 10
    mock_litellm.return_value.usage.completion_tokens = 5
    result = await a_client().call("prompt")
    assert isinstance(result, LLMResponse)
    assert result.content == "LLM finding"
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 5


@pytest.mark.asyncio
async def test_call_retries_on_service_unavailable(mock_litellm):
    good_response = MagicMock()
    good_response.choices[0].message.content = "Finding after retry"
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_litellm.side_effect = [
        ServiceUnavailableError(
            message="overloaded",
            llm_provider="gemini",
            model="gemini-2.0-flash",
            response=mock_response,
        ),
        good_response,
    ]
    result = await a_client().call("any prompt")
    assert isinstance(result, LLMResponse)
    assert result.content == "Finding after retry"
    assert mock_litellm.await_count == 2
