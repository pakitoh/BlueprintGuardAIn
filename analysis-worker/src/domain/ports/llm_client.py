from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    async def call(self, prompt: str) -> str:
        pass
