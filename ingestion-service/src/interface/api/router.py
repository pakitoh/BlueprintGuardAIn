import hashlib
import hmac
import json

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.application.use_cases.process_webhook import ProcessWebhookUseCase
from src.config import settings
from src.domain.exceptions import MappingError, UnsupportedEventError
from src.infrastructure.tracing.instrumented_process_webhook import (
    InstrumentedProcessWebhookUseCase,
)
from src.interface.api.dto import GithubWebhookDTO

logger = structlog.get_logger()
router = APIRouter()


def _verify_signature(raw_body: bytes, signature: str | None) -> None:
    """Verify GitHub's X-Hub-Signature-256 against the raw body. Always required:
    a missing secret is a server misconfiguration, a missing/bad signature is a
    rejected request."""
    secret = settings.webhook_secret
    if not secret:
        logger.error("webhook_secret_not_configured")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")
    expected = (
        "sha256="
        + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    )
    if signature is None or not hmac.compare_digest(expected, signature):
        logger.warning("webhook_signature_invalid")
        raise HTTPException(status_code=401, detail="Invalid signature")


def get_process_webhook_use_case(request: Request) -> ProcessWebhookUseCase:
    """Dependency provider for the ProcessWebhookUseCase."""
    factory = getattr(request.app.state, "factory", None)
    if factory is None:
        raise RuntimeError("InfrastructureFactory not initialized in app state")
    return InstrumentedProcessWebhookUseCase(repository=factory.code_change_repository)


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe: the process is up and serving."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> JSONResponse:
    """Readiness probe: reports 503 until the Kafka producer is started."""
    factory = getattr(request.app.state, "factory", None)
    if factory is not None:
        try:
            if factory.code_change_repository.is_ready():
                return JSONResponse(status_code=200, content={"status": "ready"})
        except RuntimeError:
            pass
    return JSONResponse(status_code=503, content={"status": "not_ready"})


@router.get("/version")
async def version(request: Request) -> dict[str, str]:
    return {"service": "ingestion-service", "version": request.app.state.version}


@router.post("/webhooks/github", status_code=202, response_model=None)
async def github_webhook(
    request: Request,
    x_github_event: str = Header(...),
    x_hub_signature_256: str | None = Header(None),
    use_case: ProcessWebhookUseCase = Depends(get_process_webhook_use_case),
) -> dict[str, str] | Response:
    raw_body = await request.body()
    _verify_signature(raw_body, x_hub_signature_256)
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as e:
        logger.warning("webhook_invalid_json", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid JSON body") from e
    try:
        GithubWebhookDTO.model_validate(payload)
    except ValidationError as e:
        logger.warning("webhook_validation_failed", error=str(e))
        raise HTTPException(status_code=422, detail=e.errors()) from e
    try:
        await use_case.execute(payload, event_type=x_github_event)
    except UnsupportedEventError:
        # Well-formed but an event we don't act on (e.g. ping, star). Acknowledge
        # with 204 so GitHub marks the delivery successful and does not retry.
        logger.info("webhook_event_ignored", event_type=x_github_event)
        return Response(status_code=204)
    except MappingError as e:
        logger.warning("webhook_processing_failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("unexpected_error", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error") from e
    return {"status": "accepted"}
