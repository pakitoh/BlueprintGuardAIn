from abc import ABC, abstractmethod
from typing import AsyncIterator
from src.domain.entities import CodeChange


class CodeChangeSource(ABC):
    @abstractmethod
    def listen(self) -> AsyncIterator[CodeChange]:
        """Streams incoming code change events."""
        pass
