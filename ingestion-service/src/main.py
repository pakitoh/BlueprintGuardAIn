from fastapi import FastAPI
from contextlib import asynccontextmanager
import structlog
from aiokafka import AIOKafkaProducer

from src.interface.api.router import router
from src.config import settings
from src.infrastructure.observability import setup_observability

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Observability (OTLP Tracing & Metrics)
    setup_observability(app)

    # Composition Root: Initialize global infrastructure
    logger.debug("starting_kafka_producer", servers=settings.kafka_bootstrap_servers)
    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
    await producer.start()

    # Store in app state so dependencies can access it
    app.state.kafka_producer = producer

    try:
        yield
    finally:
        logger.debug("stopping_kafka_producer")
        await producer.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# Mount the router (Controller)
app.include_router(router)

if __name__ == "__main__":
    import uvicorn

    # log_config=None prevents uvicorn from overriding our custom logging setup
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None)
