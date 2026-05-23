from unittest.mock import AsyncMock

import pytest


@pytest.fixture(autouse=True)
def mock_kafka(mocker):
    mock_consumer_class = mocker.patch(
        "src.infrastructure.kafka.analysis_result_source.AIOKafkaConsumer"
    )

    mock_consumer = mock_consumer_class.return_value
    mock_consumer.start = AsyncMock()
    mock_consumer.stop = AsyncMock()
    mock_consumer.__aiter__.return_value = []

    return {"consumer": mock_consumer}
