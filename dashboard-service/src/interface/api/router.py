import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import structlog
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse

from src.application.use_cases.trigger_analysis import trigger_analysis
from src.application.use_cases.trigger_replay import trigger_replay
from src.config import settings
from src.domain.entities import AnalysisRecord
from src.infrastructure.github.commit_picker import CURATED_REPOS, fetch_commit_diff

STATIC_DIR = Path(__file__).parent.parent / "static"

logger = structlog.get_logger()
router = APIRouter()


@router.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@router.get("/static/style.css")
async def stylesheet() -> FileResponse:
    return FileResponse(STATIC_DIR / "style.css", media_type="text/css")


@router.get("/static/app.js")
async def javascript() -> FileResponse:
    return FileResponse(STATIC_DIR / "app.js", media_type="application/javascript")


@router.get("/static/api.js")
async def javascript_api() -> FileResponse:
    return FileResponse(STATIC_DIR / "api.js", media_type="application/javascript")


@router.get("/static/render.js")
async def javascript_render() -> FileResponse:
    return FileResponse(STATIC_DIR / "render.js", media_type="application/javascript")


@router.get("/static/logo.png")
async def logo() -> FileResponse:
    return FileResponse(STATIC_DIR / "logo.png", media_type="image/png")


@router.get("/favicon.ico", include_in_schema=False)
async def favicon() -> FileResponse:
    return FileResponse(STATIC_DIR / "logo.png", media_type="image/png")


@router.get("/api/events")
async def sse(request: Request) -> StreamingResponse:
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=20)
    request.app.state.sse_subscribers.add(queue)

    async def generate() -> AsyncIterator[str]:
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"event: analysis_updated\ndata: {data}\n\n"
                except TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            request.app.state.sse_subscribers.discard(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/version")
async def version(request: Request) -> dict[str, str]:
    return {"service": "dashboard-service", "version": request.app.state.version}


@router.post("/api/analyses", response_model=AnalysisRecord, status_code=202)
async def create_analysis(request: Request) -> AnalysisRecord:
    try:
        return await trigger_analysis(
            repo=request.app.state.repo,
            ingestion_url=settings.ingestion_url,
            github_token=settings.github_token,
            webhook_secret=settings.webhook_secret,
        )
    except Exception as e:
        logger.error("trigger_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/curated-repos")
async def list_curated_repos() -> list[dict[str, str]]:
    return [{"repo": r, "language": lang} for r, lang in CURATED_REPOS]


@router.post("/api/replay", response_model=AnalysisRecord, status_code=202)
async def create_replay(request: Request) -> AnalysisRecord:
    body = await request.json()
    repo_name = (body.get("repository") or "").strip()
    if not repo_name:
        raise HTTPException(status_code=422, detail="repository is required")
    try:
        return await trigger_replay(
            repo_name=repo_name,
            repo=request.app.state.repo,
            ingestion_url=settings.ingestion_url,
            github_token=settings.github_token,
            webhook_secret=settings.webhook_secret,
            progress_repo=request.app.state.replay_progress_repo,
            page_cache=request.app.state.replay_page_cache,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        logger.error("replay_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/analyses", response_model=list[AnalysisRecord])
async def list_analyses(request: Request) -> list[AnalysisRecord]:
    return await request.app.state.repo.list_all()


@router.get("/api/analyses/{id}", response_model=AnalysisRecord)
async def get_analysis(id: str, request: Request) -> AnalysisRecord:
    record = await request.app.state.repo.get(id)
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    return record


@router.get("/api/analyses/{id}/diff", response_class=PlainTextResponse)
async def get_analysis_diff(id: str, request: Request) -> str:
    record: AnalysisRecord | None = await request.app.state.repo.get(id)
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        diff = await fetch_commit_diff(
            record.repository, record.sha, settings.github_token
        )
    except Exception as e:
        logger.error("diff_fetch_failed", id=id, error=str(e))
        raise HTTPException(
            status_code=502, detail="Failed to fetch diff from GitHub"
        ) from e
    return diff
