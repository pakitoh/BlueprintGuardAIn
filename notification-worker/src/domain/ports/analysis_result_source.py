from abc import ABC, abstractmethod
from typing import AsyncIterator
from src.domain.entities import AnalysisResult


class AnalysisResultSource(ABC):
    @abstractmethod
    def listen(self) -> AsyncIterator[AnalysisResult]:
        """Streams incoming analysis result events."""
        pass
