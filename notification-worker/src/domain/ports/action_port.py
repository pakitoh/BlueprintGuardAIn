from abc import ABC, abstractmethod

from src.domain.entities import AnalysisResult


class ActionPort(ABC):
    @abstractmethod
    async def execute(self, result: AnalysisResult) -> None:
        """Executes the action for the given analysis result."""
        pass
