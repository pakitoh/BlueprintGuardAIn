from unittest.mock import AsyncMock, MagicMock

import pytest
from opentelemetry import trace

from src.infrastructure.kafka.analysis_result_source import KafkaAnalysisResultSource


def _make_source(messages, mocker):
    source = KafkaAnalysisResultSource(
        bootstrap_servers="localhost:9092",
        topic="analysis-results",
        group_id="test",
        schema_client=MagicMock(),
        dlq_topic="analysis-results-dlq",
    )

    class _Consumer:
        commit = AsyncMock()

        def __aiter__(self):
            async def _gen():
                for msg in messages:
                    yield msg

            return _gen()

    source.consumer = _Consumer()
    mocker.patch.object(
        source,
        "_deserialize_avro",
        return_value={
            "repository": "org/repo",
            "sha": "sha123",
            "status": "COMPLETED",
            "findings": [],
            "timestamp": "2026-01-01T00:00:00",
        },
    )
    return source


@pytest.mark.asyncio
async def test_listen_propagates_trace_context_from_headers(mocker):
    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    traceparent = f"00-{trace_id}-00f067aa0ba902b7-01".encode()
    msg = MagicMock()
    msg.headers = [("traceparent", traceparent)]

    source = _make_source([msg], mocker)

    captured = []
    async for _ in source.listen():
        ctx = trace.get_current_span().get_span_context()
        if ctx.is_valid:
            captured.append(format(ctx.trace_id, "032x"))

    assert captured == [trace_id]


@pytest.mark.asyncio
async def test_listen_yields_entity_when_no_headers(mocker):
    msg = MagicMock()
    msg.headers = []

    source = _make_source([msg], mocker)

    count = 0
    async for _ in source.listen():
        count += 1

    assert count == 1


@pytest.mark.asyncio
async def test_listen_commits_offset_after_each_processed_message(mocker):
    msg = MagicMock()
    msg.headers = []
    source = _make_source([msg], mocker)

    async for _ in source.listen():
        pass

    source.consumer.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_listen_routes_undecodable_message_to_dlq_and_commits(mocker):
    msg = MagicMock()
    msg.headers = []
    source = _make_source([msg], mocker)
    source._dlq_producer = AsyncMock()
    mocker.patch.object(
        source, "_deserialize_avro", side_effect=ValueError("bad payload")
    )

    yielded = [r async for r in source.listen()]

    assert yielded == []  # poison message is not yielded downstream
    source._dlq_producer.send_and_wait.assert_awaited_once()
    source.consumer.commit.assert_awaited_once()  # advances past the poison message
