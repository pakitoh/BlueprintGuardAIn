from fastapi import FastAPI
from contextlib import asynccontextmanager
import structlog

from src.interface.api.router import router
from src.config import settings
from src.infrastructure.instrumentation import instrument_app, uvicorn_log_config
from src.infrastructure.factory import InfrastructureFactory


@asynccontextmanager
async def lifespan(app: FastAPI):
    factory = InfrastructureFactory()
    code_change_repo = factory.create_code_change_repository()
    await code_change_repo.start()
    app.state.code_change_repo = code_change_repo
    try:
        yield
    finally:
        await code_change_repo.stop()


# Initialize app
app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(router)
instrument_app(app)

logger = structlog.get_logger()

if __name__ == "__main__":
    import uvicorn

    logger.debug("starting_uvicorn_server", port=settings.port)
    uvicorn.run(app, host="0.0.0.0", port=settings.port, log_config=uvicorn_log_config)
