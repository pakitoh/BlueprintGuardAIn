import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture(autouse=True)
def mock_litellm(mocker):
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Default mocked finding"
    mock_router = MagicMock()
    mock_router.acompletion = AsyncMock(return_value=mock_response)
    mocker.patch(
        "src.infrastructure.llm.litellm_client.Router", return_value=mock_router
    )
    return mock_router.acompletion


@pytest.fixture(autouse=True)
def mock_litellm_embedding(mocker):
    mock_response = MagicMock()
    mock_response.data = [{"embedding": [0.1] * 768}]
    mock_router = MagicMock()
    mock_router.aembedding = AsyncMock(return_value=mock_response)
    mocker.patch(
        "src.infrastructure.llm.litellm_embedder.Router", return_value=mock_router
    )
    return mock_router.aembedding


@pytest.fixture(autouse=True)
def mock_asyncpg(mocker):
    mock_pool = AsyncMock()
    mock_pool.fetch = AsyncMock(return_value=[])
    mock_pool.execute = AsyncMock()
    mock_pool.close = AsyncMock()
    return mocker.patch(
        "src.infrastructure.pgvector.pgvector_findings_store.asyncpg.create_pool",
        new_callable=AsyncMock,
        return_value=mock_pool,
    )


@pytest.fixture(autouse=True)
def mock_kafka(mocker):
    mock_consumer_class = mocker.patch(
        "src.infrastructure.kafka.code_change_source.AIOKafkaConsumer"
    )
    mock_producer_class = mocker.patch(
        "src.infrastructure.kafka.analysis_result_repository.AIOKafkaProducer"
    )

    mock_consumer = mock_consumer_class.return_value
    mock_consumer.start = AsyncMock()
    mock_consumer.stop = AsyncMock()
    mock_consumer.__aiter__.return_value = []

    mock_producer = mock_producer_class.return_value
    mock_producer.start = AsyncMock()
    mock_producer.stop = AsyncMock()
    mock_producer.send_and_wait = AsyncMock()

    return {"consumer": mock_consumer, "producer": mock_producer}
