from abc import ABC, abstractmethod
from src.domain.entities import AnalysisResult


class AnalysisResultRepository(ABC):
    @abstractmethod
    async def save(self, result: AnalysisResult) -> None:
        """Saves an analysis result."""
        pass
