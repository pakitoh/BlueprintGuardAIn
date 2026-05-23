from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from src.config import settings
from src.infrastructure.factory import InfrastructureFactory
from src.infrastructure.instrumentation import (
    instrument_app,
    resolve_commit_sha,
    uvicorn_log_config,
)
from src.interface.api.router import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.version = resolve_commit_sha()
    factory = InfrastructureFactory()
    await factory.start()
    app.state.factory = factory
    try:
        yield
    finally:
        await factory.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(router)
instrument_app(app)

logger = structlog.get_logger()

if __name__ == "__main__":
    import uvicorn

    logger.debug("starting_uvicorn_server", port=settings.port)
    uvicorn.run(app, host="0.0.0.0", port=settings.port, log_config=uvicorn_log_config)
