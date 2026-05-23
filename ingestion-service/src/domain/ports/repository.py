from abc import ABC, abstractmethod

from src.domain.entities.code_change import CodeChange


class CodeChangeRepository(ABC):
    @abstractmethod
    async def save(self, code_change: CodeChange) -> None:
        """Persists a CodeChange event."""
        pass
