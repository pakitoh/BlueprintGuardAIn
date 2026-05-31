from abc import ABC, abstractmethod

from src.domain.entities.code_change import CodeChange


class CodeChangeRepository(ABC):
    @abstractmethod
    async def save(self, code_change: CodeChange) -> None:
        """Persists a CodeChange event."""
        pass

    @abstractmethod
    def is_ready(self) -> bool:
        """Returns True when the repository is started and able to accept writes."""
        pass
