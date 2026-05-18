from abc import ABC, abstractmethod
from typing import List

from src.domain.entities import CodeChange


class CodeAnalyzer(ABC):
    @abstractmethod
    async def analyze(self, change: CodeChange) -> List[str]:
        """Analyzes a code change and returns a list of findings."""
        pass
