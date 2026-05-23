from unittest.mock import MagicMock

import pytest
from opentelemetry import trace

from src.infrastructure.kafka.analysis_result_source import KafkaAnalysisResultSource


def _make_source(messages, mocker):
    source = KafkaAnalysisResultSource(
        bootstrap_servers="localhost:9092",
        topic="analysis-results",
        group_id="test",
        schema_client=MagicMock(),
    )

    class _Consumer:
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
