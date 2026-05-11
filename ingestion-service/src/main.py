from fastapi import FastAPI
from contextlib import asynccontextmanager
import structlog
from aiokafka import AIOKafkaProducer

from src.interface.api.router import router
from src.config import settings
from src.infrastructure.observability import setup_logging, instrument_app

# Initialize global logging BEFORE any library (like uvicorn) can start logging
logging_config = setup_logging()

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize OTEL Tracing & Metrics instrumentation
    instrument_app(app)

    # Composition Root: Initialize global infrastructure
    # In tests, we might want to skip Kafka producer start
    if not getattr(app.state, "skip_kafka_setup", False):
        logger.debug(
            "starting_kafka_producer", servers=settings.kafka_bootstrap_servers
        )
        producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
        await producer.start()
        app.state.kafka_producer = producer
    else:
        logger.debug("skipping_kafka_producer_setup_for_test")

    try:
        yield
    finally:
        if not getattr(app.state, "skip_kafka_setup", False):
            logger.debug("stopping_kafka_producer")
            await app.state.kafka_producer.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# Mount the router (Controller)
app.include_router(router)

if __name__ == "__main__":
    import uvicorn

    # log_config=logging_config prevents uvicorn from overriding our custom logging setup
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=logging_config)
