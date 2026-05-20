import structlog
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse

from src.application.use_cases.trigger_analysis import trigger_analysis
from src.config import settings
from src.domain.entities import AnalysisRecord
from src.infrastructure.github.commit_picker import fetch_commit_diff

logger = structlog.get_logger()
router = APIRouter()


@router.get("/")
async def index():
    return FileResponse("src/interface/static/index.html")


@router.get("/static/style.css")
async def stylesheet():
    return FileResponse("src/interface/static/style.css", media_type="text/css")


@router.get("/static/app.js")
async def javascript():
    return FileResponse("src/interface/static/app.js", media_type="application/javascript")


@router.get("/static/logo.png")
async def logo():
    return FileResponse("src/interface/static/logo.png", media_type="image/png")


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/api/analyses", response_model=AnalysisRecord, status_code=202)
async def create_analysis(request: Request):
    try:
        return await trigger_analysis(
            store=request.app.state.store,
            ingestion_url=settings.ingestion_url,
            github_token=settings.github_token,
        )
    except Exception as e:
        logger.error("trigger_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/analyses", response_model=list[AnalysisRecord])
async def list_analyses(request: Request):
    return sorted(
        request.app.state.store.values(),
        key=lambda r: r.created_at,
        reverse=True,
    )


@router.get("/api/analyses/{id}", response_model=AnalysisRecord)
async def get_analysis(id: str, request: Request):
    record = request.app.state.store.get(id)
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    return record


@router.get("/api/analyses/{id}/diff", response_class=PlainTextResponse)
async def get_analysis_diff(id: str, request: Request):
    record: AnalysisRecord | None = request.app.state.store.get(id)
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        diff = await fetch_commit_diff(record.repository, record.sha, settings.github_token)
    except Exception as e:
        logger.error("diff_fetch_failed", id=id, error=str(e))
        raise HTTPException(status_code=502, detail="Failed to fetch diff from GitHub")
    return diff
