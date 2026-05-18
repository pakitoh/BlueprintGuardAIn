from abc import ABC, abstractmethod
from typing import List


class Embedder(ABC):
    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        pass
