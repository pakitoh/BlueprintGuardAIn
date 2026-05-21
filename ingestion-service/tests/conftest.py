import pytest
from unittest.mock import AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.interface.api.router import router, get_process_webhook_use_case
from src.application.use_cases.process_webhook import ProcessWebhookUseCase


@pytest.fixture(autouse=True)
def mock_kafka_producer(mocker):
    """
    Globally patches AIOKafkaProducer to prevent network calls during tests.
    The 'autouse=True' ensures this is applied to every test automatically.
    """
    # Patch the producer where it is imported/used in main.py
    mock_class = mocker.patch("aiokafka.AIOKafkaProducer")

    # Configure the instance returned by the class
    mock_instance = mock_class.return_value
    mock_instance.start = AsyncMock()
    mock_instance.stop = AsyncMock()
    mock_instance.send_and_wait = AsyncMock()

    return mock_instance


@pytest.fixture(autouse=True)
def mock_schema_registry_client(mocker):
    """
    Globally patches SchemaRegistryClient to prevent network calls during tests.
    """
    mock_class = mocker.patch("schema_registry.client.SchemaRegistryClient")
    mock_instance = mock_class.return_value
    # Mock any methods if needed, but for now, just prevent initialization issues
    return mock_instance


@pytest.fixture(autouse=True)
def mock_otlp_exporters(mocker):
    """
    Globally patches OTLP exporters to prevent network calls during tests.
    """
    mocker.patch("opentelemetry.exporter.otlp.proto.grpc._log_exporter.OTLPLogExporter")
    mocker.patch(
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter"
    )
    mocker.patch(
        "opentelemetry.exporter.otlp.proto.grpc.metric_exporter.OTLPMetricExporter"
    )


@pytest.fixture
def mock_use_case():
    return AsyncMock(spec=ProcessWebhookUseCase)


@pytest.fixture
def test_app(mock_use_case):
    # Create a test app without the lifespan to avoid Kafka and OTLP connections
    app = FastAPI()
    app.include_router(router)
    app.state.version = "test-sha"
    # Setup the app to use our mock use case
    app.dependency_overrides[get_process_webhook_use_case] = lambda: mock_use_case
    yield app
    app.dependency_overrides = {}


@pytest.fixture
def client(test_app):
    with TestClient(test_app) as c:
        yield c
