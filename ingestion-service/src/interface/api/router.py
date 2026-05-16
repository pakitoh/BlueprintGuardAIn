from fastapi import APIRouter, Header, Depends, HTTPException, Request
import structlog

from src.interface.api.dto import GithubWebhookDTO
from src.application.use_cases.process_webhook import ProcessWebhookUseCase
from src.domain.exceptions import MappingError

logger = structlog.get_logger()
router = APIRouter()


def get_process_webhook_use_case(request: Request) -> ProcessWebhookUseCase:
    """Dependency provider for the ProcessWebhookUseCase."""
    # We now fetch the pure Domain Repository from the app state
    code_change_repo = getattr(request.app.state, "code_change_repo", None)

    if code_change_repo is None:
        raise RuntimeError("CodeChangeRepository not initialized in app state")

    return ProcessWebhookUseCase(repository=code_change_repo)


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
