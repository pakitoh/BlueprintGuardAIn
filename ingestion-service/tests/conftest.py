import pytest
from unittest.mock import AsyncMock

@pytest.fixture(autouse=True)
def mock_kafka_producer(mocker):
    """
    Globally patches AIOKafkaProducer to prevent network calls during tests.
    The 'autouse=True' ensures this is applied to every test automatically.
    """
    # Patch the producer where it is imported/used in main.py
    mock_class = mocker.patch("src.main.AIOKafkaProducer")
    
    # Configure the instance returned by the class
    mock_instance = mock_class.return_value
    mock_instance.start = AsyncMock()
    mock_instance.stop = AsyncMock()
    mock_instance.send_and_wait = AsyncMock()
    
    return mock_instance
