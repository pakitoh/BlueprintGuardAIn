import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture(autouse=True)
def mock_litellm(mocker):
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Default mocked finding"
    return mocker.patch(
        "src.infrastructure.llm.litellm_code_analyzer.acompletion",
        new_callable=AsyncMock,
        return_value=mock_response,
    )


@pytest.fixture(autouse=True)
def mock_kafka(mocker):
    """
    Globally patches Kafka Consumer and Producer to prevent network calls during tests.
    """
    mock_consumer_class = mocker.patch(
        "src.infrastructure.kafka.code_change_source.AIOKafkaConsumer"
    )
    mock_producer_class = mocker.patch(
        "src.infrastructure.kafka.analysis_result_repository.AIOKafkaProducer"
    )

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
