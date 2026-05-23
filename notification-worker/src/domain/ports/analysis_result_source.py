from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from src.domain.entities import AnalysisResult


class AnalysisResultSource(ABC):
    @abstractmethod
    def listen(self) -> AsyncIterator[AnalysisResult]:
        """Streams incoming analysis result events."""
        pass
