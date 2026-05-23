from abc import ABC, abstractmethod

from src.domain.entities import CodeChange


class CodeAnalyzer(ABC):
    @abstractmethod
    async def analyze(self, change: CodeChange) -> tuple[list[str], str]:
        """Analyzes a code change and returns (findings, status)
        where status is COMPLETED or FAILED."""
        pass
