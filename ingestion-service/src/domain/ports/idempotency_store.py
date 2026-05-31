from abc import ABC, abstractmethod


class IdempotencyStore(ABC):
    @abstractmethod
    def is_duplicate(self, key: str) -> bool:
        """Return True if key has already been processed (still within retention)."""

    @abstractmethod
    def mark_processed(self, key: str) -> None:
        """Record key as processed so future deliveries with it are deduplicated."""
