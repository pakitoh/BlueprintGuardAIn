from abc import ABC, abstractmethod
from src.domain.entities import AnalysisResult


class AnalysisResultRepository(ABC):
    @abstractmethod
    async def start(self) -> None:
        """Starts the repository infrastructure."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stops the repository infrastructure."""
        pass

    @abstractmethod
    async def save(self, result: AnalysisResult) -> None:
        """Saves an analysis result."""
        pass
