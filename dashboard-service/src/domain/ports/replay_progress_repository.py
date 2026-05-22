from abc import ABC, abstractmethod

from src.domain.entities import ReplayProgress


class ReplayProgressRepository(ABC):
    @abstractmethod
    async def get(self, repository: str) -> ReplayProgress | None: ...

    @abstractmethod
    async def save(self, progress: ReplayProgress) -> None: ...
