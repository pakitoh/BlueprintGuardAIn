from abc import ABC, abstractmethod
from typing import List

from src.domain.entities import CodeChange, PastFinding


class FindingsStore(ABC):
    @abstractmethod
    async def find_similar(self, change: CodeChange, limit: int = 3) -> List[PastFinding]:
        pass

    @abstractmethod
    async def save(self, change: CodeChange, findings: List[str]) -> None:
        pass
