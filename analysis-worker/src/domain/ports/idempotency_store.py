from abc import ABC, abstractmethod


class IdempotencyStore(ABC):
    """Tracks which code changes have already been analysed, so a redelivered
    Kafka event does not trigger a second (billable) LLM analysis."""

    @abstractmethod
    async def is_processed(self, key: str) -> bool: ...

    @abstractmethod
    async def mark_processed(self, key: str) -> None: ...
