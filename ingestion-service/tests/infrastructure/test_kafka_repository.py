import asyncio
import pytest
import struct
import json
from unittest.mock import AsyncMock, MagicMock
from src.domain.entities.code_change import CodeChange
from src.infrastructure.kafka.repository import KafkaCodeChangeRepository
from src.domain.exceptions import RepositoryError


@pytest.fixture
def mock_producer():
    """Mock Kafka producer with Async methods."""
    return AsyncMock()


@pytest.fixture
def mock_schema_client():
    """Mock Schema Registry client."""
    client = MagicMock()
    client.register.return_value = 123  # Mock Schema ID
    return client


@pytest.fixture
def dummy_schema():
    """A minimal valid Avro schema matching the CodeChange structure."""
    return json.dumps(
        {
            "type": "record",
            "name": "CodeChange",
            "fields": [
                {"name": "repository", "type": "string"},
                {"name": "ref", "type": "string"},
                {"name": "target_sha", "type": "string"},
                {"name": "event_type", "type": "string"},
                {"name": "raw_payload", "type": "string"},
            ],
        }
    )


@pytest.fixture
def repo(mock_producer, mock_schema_client, dummy_schema):
    """The repository instance under test."""
    return KafkaCodeChangeRepository(
        producer=mock_producer,
        topic="test-topic",
        schema_client=mock_schema_client,
        schema_str=dummy_schema,
    )


@pytest.mark.asyncio
async def test_kafka_repository_should_send_avro_to_topic(repo, mock_producer):
    # Arrange
    change = CodeChange(
        repository="paco/blueprint",
        ref="main",
        target_sha="sha123",
        event_type="push",
        raw_payload={"some": "data"},
    )

    # Act
    await repo.save(change)

    # Assert
    mock_producer.send_and_wait.assert_called_once()
    args, kwargs = mock_producer.send_and_wait.call_args

    # 1. Verify Topic
    assert args[0] == "test-topic"

    # 2. Verify Key (Repository Name)
    assert kwargs["key"] == b"paco/blueprint"

    # 3. Verify Avro Wire Format (Magic Byte + Schema ID)
    value = kwargs["value"]
    magic_byte, schema_id = struct.unpack(">bi", value[:5])
    assert magic_byte == 0
    assert schema_id == 123
    assert len(value) > 5  # Ensure there is binary data after the header


@pytest.mark.asyncio
async def test_kafka_repository_should_raise_repository_error_on_connection_failure(
    repo, mock_producer
):
    # Arrange
    mock_producer.send_and_wait.side_effect = Exception("Kafka connection failed")
    change = CodeChange(
        repository="repo",
        ref="ref",
        target_sha="sha",
        event_type="push",
        raw_payload={},
    )

    # Act & Assert
    with pytest.raises(RepositoryError, match="Failed to save code change to Kafka"):
        await repo.save(change)


@pytest.mark.asyncio
async def test_kafka_repository_should_raise_repository_error_on_timeout(
    repo, mock_producer
):
    # Arrange
    mock_producer.send_and_wait.side_effect = asyncio.TimeoutError()
    change = CodeChange(
        repository="repo",
        ref="ref",
        target_sha="sha",
        event_type="push",
        raw_payload={},
    )

    # Act & Assert
    with pytest.raises(RepositoryError, match="Timeout"):
        await repo.save(change)
