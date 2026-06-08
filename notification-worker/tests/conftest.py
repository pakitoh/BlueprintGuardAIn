from unittest.mock import AsyncMock

import pytest


@pytest.fixture(autouse=True)
def mock_kafka(mocker):
    mock_consumer_class = mocker.patch(
        "src.infrastructure.kafka.analysis_result_source.AIOKafkaConsumer"
    )
    mock_dlq_producer_class = mocker.patch(
        "src.infrastructure.kafka.analysis_result_source.AIOKafkaProducer"
    )

    mock_consumer = mock_consumer_class.return_value
    mock_consumer.start = AsyncMock()
    mock_consumer.stop = AsyncMock()
    mock_consumer.commit = AsyncMock()
    mock_consumer.__aiter__.return_value = []

    mock_dlq_producer = mock_dlq_producer_class.return_value
    mock_dlq_producer.start = AsyncMock()
    mock_dlq_producer.stop = AsyncMock()
    mock_dlq_producer.send_and_wait = AsyncMock()

    return {"consumer": mock_consumer, "dlq_producer": mock_dlq_producer}
