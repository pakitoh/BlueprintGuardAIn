import asyncio
import pytest
import struct
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from src.domain.entities import AnalysisResult
from src.infrastructure.kafka.repository import KafkaAnalysisRepository


@pytest.fixture
def mock_producer():
    """Mock Kafka producer with Async methods."""
    return AsyncMock()


@pytest.fixture
def mock_schema_client():
    """Mock Schema Registry client."""
    client = MagicMock()
    client.register.return_value = 456  # Mock Schema ID for AnalysisResult
    return client


@pytest.fixture
def dummy_schema():
    """A minimal valid Avro schema matching the AnalysisResult structure."""
    return json.dumps(
        {
            "type": "record",
            "name": "AnalysisResult",
            "fields": [
                {"name": "repository", "type": "string"},
                {"name": "sha", "type": "string"},
                {"name": "status", "type": "string"},
                {"name": "findings", "type": {"type": "array", "items": "string"}},
                {"name": "timestamp", "type": "string"},
            ],
        }
    )


@pytest.fixture
def repo(mock_producer, mock_schema_client, dummy_schema):
    """The repository instance under test."""
    return KafkaAnalysisRepository(
        producer=mock_producer,
        topic="analysis-results-topic",
        schema_client=mock_schema_client,
        schema_str=dummy_schema,
    )


@pytest.mark.asyncio
async def test_kafka_analysis_repository_should_send_avro_to_topic(repo, mock_producer):
    # Arrange
    result = AnalysisResult(
        repository="paco/blueprint",
        sha="sha123",
        status="COMPLETED",
        findings=["All good", "Clean code"],
        timestamp=datetime.now(),
    )

    # Act
    await repo.save(result)

    # Assert
    mock_producer.send_and_wait.assert_called_once()
    args, kwargs = mock_producer.send_and_wait.call_args

    # 1. Verify Topic
    assert args[0] == "analysis-results-topic"

    # 2. Verify Key (Repository Name)
    assert kwargs["key"] == b"paco/blueprint"

    # 3. Verify Avro Wire Format (Magic Byte + Schema ID)
    value = kwargs["value"]
    magic_byte, schema_id = struct.unpack(">bi", value[:5])
    assert magic_byte == 0
    assert schema_id == 456
    assert len(value) > 5


@pytest.mark.asyncio
async def test_kafka_analysis_repository_should_raise_error_on_failure(
    repo, mock_producer
):
    # Arrange
    mock_producer.send_and_wait.side_effect = Exception("Kafka down")
    result = AnalysisResult(
        repository="repo",
        sha="sha",
        status="FAIL",
        findings=[],
        timestamp=datetime.now(),
    )

    # Act & Assert
    with pytest.raises(Exception, match="Kafka down"):
        await repo.save(result)
