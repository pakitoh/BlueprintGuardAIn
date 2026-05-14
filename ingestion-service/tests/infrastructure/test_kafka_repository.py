import asyncio
import pytest
import json
from unittest.mock import AsyncMock
from src.domain.entities.code_change import CodeChange
from src.infrastructure.kafka.repository import KafkaCodeChangeRepository
from src.domain.exceptions import RepositoryError


@pytest.mark.asyncio
async def test_kafka_repository_should_send_json_to_topic():
    mock_producer = AsyncMock()
    repo = KafkaCodeChangeRepository(producer=mock_producer, topic="test-topic")
    change = CodeChange(
        repository="paco/blueprint",
        ref="main",
        target_sha="sha123",
        event_type="push",
        raw_payload={"some": "data"},
    )

    await repo.save(change)

    # Check if producer.send_and_wait was called with the right topic and serialized bytes
    mock_producer.send_and_wait.assert_called_once()
    args, kwargs = mock_producer.send_and_wait.call_args
    topic = args[0]
    assert topic == "test-topic"
    key = kwargs["key"].decode("utf-8")
    assert key == "paco/blueprint"
    sent_data = json.loads(kwargs["value"].decode("utf-8"))
    assert sent_data["repository"] == "paco/blueprint"
    assert sent_data["target_sha"] == "sha123"


@pytest.mark.asyncio
async def test_kafka_repository_should_raise_repository_error_on_connection_failure():
    mock_producer = AsyncMock()
    mock_producer.send_and_wait.side_effect = Exception("Kafka connection failed")
    repo = KafkaCodeChangeRepository(producer=mock_producer, topic="test-topic")
    change = CodeChange(
        repository="paco/blueprint",
        ref="main",
        target_sha="sha123",
        event_type="push",
        raw_payload={},
    )

    with pytest.raises(RepositoryError) as exc:
        await repo.save(change)

    assert "Failed to save code change to Kafka" in str(exc.value)


@pytest.mark.asyncio
async def test_kafka_repository_should_raise_repository_error_on_timeout():
    mock_producer = AsyncMock()
    mock_producer.send_and_wait.side_effect = asyncio.TimeoutError()
    repo = KafkaCodeChangeRepository(producer=mock_producer, topic="test-topic")
    change = CodeChange(
        repository="paco/blueprint",
        ref="main",
        target_sha="sha123",
        event_type="push",
        raw_payload={},
    )

    with pytest.raises(RepositoryError) as exc:
        await repo.save(change)

    assert "Timeout" in str(exc.value)
