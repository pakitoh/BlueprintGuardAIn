import time

import structlog

from src.domain.ports.embedder import Embedder
from src.infrastructure.llm.router_factory import build_router
from src.infrastructure.metrics import embedding_duration

logger = structlog.get_logger()


class LiteLLMEmbedder(Embedder):
    def __init__(self, configs: list[tuple[str, str]]):
        self._model = configs[0][0]
        self._router = build_router(configs, num_retries=3)

    async def embed(self, text: str) -> list[float]:
        start = time.perf_counter()
        response = await self._router.aembedding(
            model="config-0",
            input=[text],
            dimensions=768,
        )
        embedding_duration.record(time.perf_counter() - start)
        return response.data[0]["embedding"]
