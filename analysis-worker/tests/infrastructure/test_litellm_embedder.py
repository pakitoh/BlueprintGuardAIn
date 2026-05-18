import pytest
from src.infrastructure.llm.litellm_embedder import LiteLLMEmbedder


def an_embedder():
    return LiteLLMEmbedder(model="gemini/gemini-embedding-2", api_key="test-key")


@pytest.mark.asyncio
async def test_embed_calls_aembedding_with_correct_params(mock_litellm_embedding):
    await an_embedder().embed("some text")
    mock_litellm_embedding.assert_awaited_once_with(
        model="gemini/gemini-embedding-2",
        input=["some text"],
        dimensions=768,
        num_retries=3,
        api_key="test-key",
    )


@pytest.mark.asyncio
async def test_embed_returns_vector_from_response(mock_litellm_embedding):
    expected = [0.5] * 768
    mock_litellm_embedding.return_value.data = [{"embedding": expected}]
    result = await an_embedder().embed("some text")
    assert result == expected
