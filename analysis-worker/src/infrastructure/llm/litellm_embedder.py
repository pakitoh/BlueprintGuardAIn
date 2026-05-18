import structlog
from typing import List
from litellm import aembedding

from src.domain.ports.embedder import Embedder

logger = structlog.get_logger()


class LiteLLMEmbedder(Embedder):
    def __init__(self, model: str, api_key: str):
        self._model = model
        self._api_key = api_key

    async def embed(self, text: str) -> List[float]:
        response = await aembedding(
            model=self._model,
            input=[text],
            api_key=self._api_key,
        )
        return response.data[0]["embedding"]
