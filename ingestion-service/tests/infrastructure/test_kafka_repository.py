import pytest
import json
from unittest.mock import AsyncMock
from src.domain.entities.code_change import CodeChange
from src.infrastructure.kafka.repository import KafkaCodeChangeRepository

@pytest.mark.asyncio
async def test_kafka_repository_should_send_json_to_topic():
    """Verify that the Kafka implementation serializes and sends the change."""
    mock_producer = AsyncMock()
    repo = KafkaCodeChangeRepository(producer=mock_producer, topic="test-topic")
    change = CodeChange(
        repository="paco/blueprint",
        ref="main",
        target_sha="sha123",
        event_type="push",
        raw_payload={"some": "data"}
    )

    await repo.save(change)

    # Check if producer.send_and_wait was called with the right topic and serialized bytes
    mock_producer.send_and_wait.assert_called_once()
    args, _ = mock_producer.send_and_wait.call_args
    topic, value = args    
    assert topic == "test-topic"
    sent_data = json.loads(value.decode("utf-8"))
    assert sent_data["repository"] == "paco/blueprint"
    assert sent_data["target_sha"] == "sha123"
