import json
import struct
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.entities.code_change import CodeChange
from src.domain.exceptions import RepositoryError
from src.infrastructure.kafka.repository import KafkaCodeChangeRepository

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
    mock_producer.send_and_wait.side_effect = TimeoutError("timeout")
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


def _a_change() -> CodeChange:
    return CodeChange(
        repository=REPOSITORY,
        ref=REF,
        target_sha=SHA,
        event_type=EVENT_TYPE,
        raw_payload={},
    )


@pytest.mark.asyncio
async def test_is_ready_reflects_producer_lifecycle(repo, mock_producer):
    assert repo.is_ready() is False
    await repo.start()
    assert repo.is_ready() is True
    await repo.stop()
    assert repo.is_ready() is False


@pytest.mark.asyncio
async def test_start_raises_repository_error_when_producer_fails(repo, mock_producer):
    mock_producer.start.side_effect = Exception("connect failed")

    with pytest.raises(RepositoryError, match="Failed to start Kafka producer"):
        await repo.start()


@pytest.mark.asyncio
async def test_save_before_start_raises_repository_error(repo):
    with pytest.raises(RepositoryError, match="not started"):
        await repo.save(_a_change())


@pytest.mark.asyncio
async def test_save_raises_when_schema_registration_fails(
    repo, mock_producer, mock_schema_client
):
    mock_schema_client.register.side_effect = Exception("registry down")
    await repo.start()

    with pytest.raises(RepositoryError):
        await repo.save(_a_change())


@pytest.mark.asyncio
async def test_schema_is_registered_only_once_across_saves(
    repo, mock_producer, mock_schema_client
):
    await repo.start()

    await repo.save(_a_change())
    await repo.save(_a_change())

    mock_schema_client.register.assert_called_once()


@pytest.mark.asyncio
async def test_save_raises_when_serialization_fails(repo, mock_producer, mocker):
    await repo.start()
    mocker.patch(
        "src.infrastructure.kafka.repository.schemaless_writer",
        side_effect=Exception("bad avro"),
    )

    with pytest.raises(RepositoryError):
        await repo.save(_a_change())
