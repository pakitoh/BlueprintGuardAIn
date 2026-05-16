import asyncio
import pytest
import struct
import json
from unittest.mock import AsyncMock, MagicMock
from src.domain.entities.code_change import CodeChange
from src.infrastructure.kafka.repository import KafkaCodeChangeRepository
from src.domain.exceptions import RepositoryError

SCHEMA_ID = 123
TOPIC = "test-topic"
REPOSITORY = "user/project"
SHA = "sha123abc"
REF = "refs/heads/main"
EVENT_TYPE = "push"


@pytest.fixture
def mock_producer(mocker):
    """Mock Kafka producer and patch the repository to use it."""
    producer = AsyncMock()
    producer.start = AsyncMock()
    producer.stop = AsyncMock()
    producer.send_and_wait = AsyncMock()
    mocker.patch(
        "src.infrastructure.kafka.repository.AIOKafkaProducer",
        return_value=producer,
    )
    return producer


@pytest.fixture
def mock_schema_client():
    """Mock Schema Registry client."""
    client = MagicMock()
    client.register.return_value = SCHEMA_ID
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
def repo(mock_schema_client, dummy_schema):
    """The repository instance under test."""
    return KafkaCodeChangeRepository(
        bootstrap_servers="test-bootstrap:9092",
        topic=TOPIC,
        schema_client=mock_schema_client,
        schema_str=dummy_schema,
    )


@pytest.mark.asyncio
async def test_kafka_repository_should_send_avro_to_topic(repo, mock_producer):
    change = CodeChange(
        repository=REPOSITORY,
        ref=REF,
        target_sha=SHA,
        event_type=EVENT_TYPE,
        raw_payload={"some": "data"},
    )
    await repo.start()

    await repo.save(change)

    mock_producer.send_and_wait.assert_called_once()
    args, kwargs = mock_producer.send_and_wait.call_args
    assert args[0] == TOPIC
    assert kwargs["key"] == REPOSITORY.encode("utf-8")
    value = kwargs["value"]
    magic_byte, schema_id = struct.unpack(">bi", value[:5])
    assert magic_byte == 0
    assert schema_id == SCHEMA_ID


@pytest.mark.asyncio
async def test_kafka_repository_should_raise_repository_error_on_connection_failure(
    repo, mock_producer
):
    mock_producer.send_and_wait.side_effect = Exception("Kafka connection failed")
    change = CodeChange(
        repository=REPOSITORY,
        ref=REF,
        target_sha=SHA,
        event_type=EVENT_TYPE,
        raw_payload={},
    )
    await repo.start()

    with pytest.raises(RepositoryError, match="Failed to save code change"):
        await repo.save(change)


@pytest.mark.asyncio
async def test_kafka_repository_should_raise_repository_error_on_timeout(
    repo, mock_producer
):
    mock_producer.send_and_wait.side_effect = asyncio.TimeoutError("timeout")
    change = CodeChange(
        repository=REPOSITORY,
        ref=REF,
        target_sha=SHA,
        event_type=EVENT_TYPE,
        raw_payload={},
    )
    await repo.start()

    with pytest.raises(RepositoryError, match="Failed to save code change"):
        await repo.save(change)
