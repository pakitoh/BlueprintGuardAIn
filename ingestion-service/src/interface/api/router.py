from fastapi import APIRouter, Header, Depends, HTTPException, Request
import structlog

from src.interface.api.dto import GithubWebhookDTO
from src.application.use_cases.process_webhook import ProcessWebhookUseCase
from src.domain.exceptions import MappingError
from src.infrastructure.kafka.repository import KafkaCodeChangeRepository
from src.config import settings

logger = structlog.get_logger()
router = APIRouter()


def get_process_webhook_use_case(request: Request) -> ProcessWebhookUseCase:
    """Dependency provider for the ProcessWebhookUseCase."""
    kafka_producer = getattr(request.app.state, "kafka_producer", None)
    schema_registry_client = getattr(request.app.state, "schema_registry_client", None)
    code_change_schema = getattr(request.app.state, "code_change_schema", None)

    if any(
        x is None for x in [kafka_producer, schema_registry_client, code_change_schema]
    ):
        raise RuntimeError("Global infrastructure not initialized in app state")

    repository = KafkaCodeChangeRepository(
        producer=kafka_producer,
        topic=settings.webhook_events_topic,
        schema_client=schema_registry_client,
        schema_str=code_change_schema,
    )
    return ProcessWebhookUseCase(repository=repository)


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/webhooks/github", status_code=202)
async def github_webhook(
    event: GithubWebhookDTO,
    x_github_event: str = Header(...),
    use_case: ProcessWebhookUseCase = Depends(get_process_webhook_use_case),
):
    payload = event.model_dump(exclude_unset=True)
    try:
        await use_case.execute(payload, event_type=x_github_event)
    except MappingError as e:
        logger.warning("webhook_processing_failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("unexpected_error", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")
    return {"status": "accepted"}
