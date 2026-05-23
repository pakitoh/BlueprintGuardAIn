from abc import ABC, abstractmethod

from src.domain.entities import CodeChange, PastFinding
from src.domain.ports.diff_fetcher import FileDiff


class FindingsStore(ABC):
    @abstractmethod
    async def find_similar(
        self,
        change: CodeChange,
        limit: int = 3,
        file_diffs: list[FileDiff] | None = None,
    ) -> list[PastFinding]:
        pass

    @abstractmethod
    async def save(
        self,
        change: CodeChange,
        findings: list[str],
        file_diffs: list[FileDiff] | None = None,
    ) -> None:
        pass
