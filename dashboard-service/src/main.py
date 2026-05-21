from contextlib import asynccontextmanager
from fastapi import FastAPI
import structlog

from src.config import settings
from src.infrastructure.factory import InfrastructureFactory
from src.infrastructure.instrumentation import instrument_app, uvicorn_log_config
from src.interface.api.router import router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    factory = InfrastructureFactory()
    app.state.factory = factory
    await factory.start()
    app.state.repo = factory.repo
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
