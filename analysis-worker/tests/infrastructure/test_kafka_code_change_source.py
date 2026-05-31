from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from opentelemetry import trace

from src.infrastructure.kafka.code_change_source import KafkaCodeChangeSource


def _make_source(messages, mocker, deserialized=None):
    source = KafkaCodeChangeSource(
        bootstrap_servers="localhost:9092",
        topic="code-changes",
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
        return_value=deserialized
        or {
            "repository": "org/repo",
            "ref": "main",
            "target_sha": "sha123",
            "event_type": "push",
            "raw_payload": "{}",
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
async def test_listen_uses_ingested_at_as_timestamp(mocker):
    msg = MagicMock()
    msg.headers = []
    ingested = "2026-05-29T10:00:00+00:00"
    source = _make_source(
        [msg],
        mocker,
        deserialized={
            "repository": "org/repo",
            "ref": "main",
            "target_sha": "sha123",
            "event_type": "push",
            "raw_payload": "{}",
            "ingested_at": ingested,
        },
    )

    changes = [c async for c in source.listen()]

    assert changes[0].timestamp == datetime.fromisoformat(ingested)


@pytest.mark.asyncio
async def test_listen_falls_back_to_now_when_ingested_at_absent(mocker):
    msg = MagicMock()
    msg.headers = []
    before = datetime.now(UTC)
    source = _make_source([msg], mocker)  # default dict has no ingested_at

    changes = [c async for c in source.listen()]

    # falls back to an aware "now" rather than raising or yielding naive
    assert changes[0].timestamp.tzinfo is not None
    assert changes[0].timestamp >= before
