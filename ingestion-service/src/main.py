from fastapi import FastAPI
from contextlib import asynccontextmanager
import structlog
from aiokafka import AIOKafkaProducer
from opentelemetry.instrumentation.aiokafka import AIOKafkaInstrumentor
from schema_registry.client import SchemaRegistryClient

from src.interface.api.router import router
from src.config import settings
from src.infrastructure.instrumentation import instrument_app, uvicorn_log_config


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.debug("starting_kafka_producer", servers=settings.kafka_bootstrap_servers)
    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
    AIOKafkaInstrumentor().instrument()

    await producer.start()

    # Initialize Schema Registry Client
    schema_registry_client = SchemaRegistryClient(url=settings.schema_registry_url)

    # Load CodeChange Schema
    with open("../schemas/CodeChange.avsc", "r") as f:
        code_change_schema = f.read()

    # Store in app state
    app.state.kafka_producer = producer
    app.state.schema_registry_client = schema_registry_client
    app.state.code_change_schema = code_change_schema

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
