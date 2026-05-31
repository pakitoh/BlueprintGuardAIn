from typing import Any

import structlog

from src.domain.entities.code_change import CodeChange
from src.domain.exceptions import UnsupportedEventError
from src.domain.ports.idempotency_store import IdempotencyStore
from src.domain.ports.repository import CodeChangeRepository

logger = structlog.get_logger()


class ProcessWebhookUseCase:
    def __init__(
        self,
        repository: CodeChangeRepository,
        idempotency_store: IdempotencyStore,
    ):
        self.repository = repository
        self._idempotency = idempotency_store

    async def execute(self, payload: dict[str, Any], event_type: str) -> None:
        logger.info("processing_webhook", event_type=event_type)
        change = self._map_event(payload, event_type)
        key = f"{change.repository}@{change.target_sha}"
        if self._idempotency.is_duplicate(key):
            logger.info(
                "duplicate_change_skipped",
                repo=change.repository,
                sha=change.target_sha,
            )
            return
        await self.repository.save(change)
        self._idempotency.mark_processed(key)
        logger.info(
            "webhook_processed_successfully",
            repo=change.repository,
            sha=change.target_sha,
        )

    def _map_event(self, payload: dict[str, Any], event_type: str) -> CodeChange:
        if event_type == "push":
            return CodeChange.from_push_event(payload)
        if event_type == "pull_request":
            return CodeChange.from_pull_request_event(payload)
        raise UnsupportedEventError(f"Unsupported event type: {event_type}")
