from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from src.config import settings
from src.domain.entities import AnalysisRecord
from src.infrastructure.factory import InfrastructureFactory
from src.infrastructure.instrumentation import (
    instrument_app,
    resolve_commit_sha,
    uvicorn_log_config,
)
from src.interface.api.router import router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.version = resolve_commit_sha()
    app.state.sse_subscribers = set()

    async def broadcast(record: AnalysisRecord) -> None:
        data = record.model_dump_json()
        for q in list(app.state.sse_subscribers):
            q.put_nowait(data)

    factory = InfrastructureFactory()
    app.state.factory = factory
    await factory.start(on_result=broadcast)
    app.state.repo = factory.repo
    app.state.replay_progress_repo = factory.replay_progress_repo
    app.state.replay_page_cache = {}
    try:
        yield
    finally:
        await factory.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(router)
instrument_app(app)

if __name__ == "__main__":
    import uvicorn

    logger.debug("starting_uvicorn_server", port=settings.port)
    uvicorn.run(app, host="0.0.0.0", port=settings.port, log_config=uvicorn_log_config)
