from typing import Dict, Any
import structlog
from src.domain.entities.code_change import CodeChange
from src.domain.ports.repository import CodeChangeRepository
from src.domain.exceptions import MappingError

logger = structlog.get_logger()


class ProcessWebhookUseCase:
    def __init__(self, repository: CodeChangeRepository):
        self.repository = repository

    async def execute(self, payload: Dict[str, Any], event_type: str) -> None:
        logger.info("processing_webhook", event_type=event_type)
        if event_type == "push":
            change = CodeChange.from_push_event(payload)
        elif event_type == "pull_request":
            change = CodeChange.from_pull_request_event(payload)
        else:
            raise MappingError(f"Unsupported event type: {event_type}")
        await self.repository.save(change)
        logger.info(
            "webhook_processed_successfully",
            repo=change.repository,
            sha=change.target_sha,
        )
