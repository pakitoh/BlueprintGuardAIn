from abc import ABC, abstractmethod

from src.domain.entities import LLMResponse


class LLMClient(ABC):
    @abstractmethod
    async def call(self, prompt: str) -> LLMResponse:
        pass
