from abc import ABC, abstractmethod
from typing import List

from src.domain.entities import CodeChange


class CodeAnalyzer(ABC):
    @abstractmethod
    async def analyze(self, change: CodeChange) -> tuple[List[str], str]:
        """Analyzes a code change and returns (findings, status) where status is COMPLETED or FAILED."""
        pass
