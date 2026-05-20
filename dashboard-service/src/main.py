from contextlib import asynccontextmanager
from fastapi import FastAPI
import structlog

from src.config import settings
from src.infrastructure.factory import InfrastructureFactory
from src.interface.api.router import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.store = {}
    factory = InfrastructureFactory()
    await factory.start(app.state.store)
    app.state.factory = factory
    try:
        yield
    finally:
        await factory.stop()


app = FastAPI(title="Blueprint GuardAIn Dashboard", lifespan=lifespan)
app.include_router(router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.port)
