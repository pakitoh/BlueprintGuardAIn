from abc import ABC, abstractmethod
from typing import AsyncIterator
from src.domain.entities import CodeChange


class CodeChangeRepository(ABC):
    @abstractmethod
    async def start(self) -> None:
        """Starts the repository infrastructure."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stops the repository infrastructure."""
        pass

    @abstractmethod
    def listen(self) -> AsyncIterator[CodeChange]:
        """Streams code changes from the repository."""
        pass
