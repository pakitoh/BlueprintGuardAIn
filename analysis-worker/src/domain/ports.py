from abc import ABC, abstractmethod
from src.domain.entities import AnalysisResult


class AnalysisRepository(ABC):
    @abstractmethod
    async def save(self, result: AnalysisResult) -> None:
        pass
