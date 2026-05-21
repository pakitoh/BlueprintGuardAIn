import time
import structlog
from typing import List
from litellm import Router

from src.domain.ports.embedder import Embedder
from src.infrastructure.metrics import embedding_duration

logger = structlog.get_logger()


class LiteLLMEmbedder(Embedder):
    def __init__(self, configs: list[tuple[str, str]]):
        self._model = configs[0][0]
        self._router = LiteLLMEmbedder._build_router(configs)

    @staticmethod
    def _build_router(configs: list[tuple[str, str]]) -> Router:
        names = [f"config-{i}" for i in range(len(configs))]
        model_list = [
            {
                "model_name": name,
                "litellm_params": {"model": model, "api_key": api_key},
            }
            for name, (model, api_key) in zip(names, configs)
        ]
        return Router(
            model_list=model_list,
            fallbacks=[{names[0]: names[1:]}] if len(names) > 1 else None,
            num_retries=3,
        )

    async def embed(self, text: str) -> List[float]:
        start = time.perf_counter()
        response = await self._router.aembedding(
            model="config-0",
            input=[text],
            dimensions=768,
        )
        embedding_duration.record(time.perf_counter() - start)
        return response.data[0]["embedding"]
