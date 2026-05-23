import pytest

from src.infrastructure.llm.litellm_embedder import LiteLLMEmbedder


def an_embedder():
    return LiteLLMEmbedder(configs=[("gemini/gemini-embedding-2", "test-key")])


@pytest.mark.asyncio
async def test_embed_calls_aembedding_with_correct_params(mock_litellm_embedding):
    await an_embedder().embed("some text")
    mock_litellm_embedding.assert_awaited_once_with(
        model="config-0",
        input=["some text"],
        dimensions=768,
    )


@pytest.mark.asyncio
async def test_embed_returns_vector_from_response(mock_litellm_embedding):
    expected = [0.5] * 768
    mock_litellm_embedding.return_value.data = [{"embedding": expected}]
    result = await an_embedder().embed("some text")
    assert result == expected
