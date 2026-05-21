from abc import ABC, abstractmethod

from src.domain.entities import AnalysisRecord


class AnalysisRepository(ABC):
    @abstractmethod
    async def save(self, record: AnalysisRecord) -> None: ...

    @abstractmethod
    async def update(self, record: AnalysisRecord) -> None: ...

    @abstractmethod
    async def get(self, id: str) -> AnalysisRecord | None: ...

    @abstractmethod
    async def get_by_repo_sha(
        self, repository: str, sha: str
    ) -> AnalysisRecord | None: ...

    @abstractmethod
    async def list_all(self) -> list[AnalysisRecord]: ...
