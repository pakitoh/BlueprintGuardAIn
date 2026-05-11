import pytest
from unittest.mock import AsyncMock

@pytest.fixture(autouse=True)
def mock_kafka(mocker):
    """
    Globally patches Kafka Consumer and Producer to prevent network calls during tests.
    """
    mock_consumer_class = mocker.patch("src.main.AIOKafkaConsumer")
    mock_producer_class = mocker.patch("src.main.AIOKafkaProducer")
    
    mock_consumer = mock_consumer_class.return_value
    mock_consumer.start = AsyncMock()
    mock_consumer.stop = AsyncMock()
    # Mocking the async iterator for the consumer
    mock_consumer.__aiter__.return_value = []

    mock_producer = mock_producer_class.return_value
    mock_producer.start = AsyncMock()
    mock_producer.stop = AsyncMock()
    mock_producer.send_and_wait = AsyncMock()
    
    return {"consumer": mock_consumer, "producer": mock_producer}
