from fastapi import FastAPI
from contextlib import asynccontextmanager
import structlog
from aiokafka import AIOKafkaProducer
from opentelemetry.instrumentation.aiokafka import AIOKafkaInstrumentor

from src.interface.api.router import router
from src.config import settings
from src.infrastructure.instrumentation import instrument_app, uvicorn_log_config


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.debug("starting_kafka_producer", servers=settings.kafka_bootstrap_servers)
    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
    AIOKafkaInstrumentor().instrument()

    await producer.start()
    app.state.kafka_producer = producer
    try:
        yield
    finally:
        logger.debug("stopping_kafka_producer")
        await app.state.kafka_producer.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(router)
instrument_app(app)

logger = structlog.get_logger()


if __name__ == "__main__":
    import uvicorn

    logger.debug("starting_uvicorn_server", servers=settings.port)
    uvicorn.run(app, host="0.0.0.0", port=settings.port, log_config=uvicorn_log_config)
