import time
import structlog
from typing import List
from litellm import aembedding

from src.domain.ports.embedder import Embedder
from src.infrastructure.metrics import embedding_duration

logger = structlog.get_logger()


class LiteLLMEmbedder(Embedder):
    def __init__(self, model: str, api_key: str):
        self._model = model
        self._api_key = api_key

    async def embed(self, text: str) -> List[float]:
        start = time.perf_counter()
        response = await aembedding(
            model=self._model,
            input=[text],
            dimensions=768,
            num_retries=3,
            api_key=self._api_key,
        )
        embedding_duration.record(time.perf_counter() - start)
        return response.data[0]["embedding"]
