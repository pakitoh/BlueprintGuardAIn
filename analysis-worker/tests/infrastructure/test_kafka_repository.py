import asyncio
import pytest
import struct
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from src.domain.entities import AnalysisResult
from src.infrastructure.kafka.analysis_result_repository import (
    KafkaAnalysisResultRepository,
)


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
def repo(mock_schema_client, dummy_schema):
    """The repository instance under test."""
    # AIOKafkaProducer is globally mocked in conftest.py
    return KafkaAnalysisResultRepository(
        bootstrap_servers="localhost:9092",
        topic="analysis-results",
        schema_client=mock_schema_client,
        schema_str=dummy_schema,
    )


@pytest.mark.asyncio
async def test_kafka_analysis_result_repository_should_send_avro_to_topic(
    repo, mock_kafka
):
    # Arrange
    result = AnalysisResult(
        repository="paco/blueprint",
        sha="sha123",
        status="COMPLETED",
        findings=["All good", "Clean code"],
        timestamp=datetime.now(),
    )

    mock_producer = mock_kafka["producer"]
    await repo.start()

    # Act
    await repo.save(result)

    # Assert
    mock_producer.send_and_wait.assert_called_once()
    args, kwargs = mock_producer.send_and_wait.call_args

    # 1. Verify Topic
    assert args[0] == "analysis-results"

    # 2. Verify Key (Repository Name)
    assert kwargs["key"] == b"paco/blueprint"

    # 3. Verify Avro Wire Format (Magic Byte + Schema ID)
    value = kwargs["value"]
    magic_byte, schema_id = struct.unpack(">bi", value[:5])
    assert magic_byte == 0
    assert schema_id == 456


@pytest.mark.asyncio
async def test_kafka_analysis_result_repository_should_raise_error_on_failure(
    repo, mock_kafka
):
    # Arrange
    mock_producer = mock_kafka["producer"]
    mock_producer.send_and_wait.side_effect = Exception("Kafka down")
    result = AnalysisResult(
        repository="repo",
        sha="sha",
        status="FAIL",
        findings=[],
        timestamp=datetime.now(),
    )

    await repo.start()

    # Act & Assert
    with pytest.raises(Exception, match="Failed to save analysis result"):
        await repo.save(result)
