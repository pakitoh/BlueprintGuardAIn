from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from opentelemetry import trace

from src.infrastructure.kafka.code_change_source import KafkaCodeChangeSource


def _make_source(messages, mocker, deserialized=None):
    source = KafkaCodeChangeSource(
        bootstrap_servers="localhost:9092",
        topic="code-changes",
        group_id="test",
        schema_client=MagicMock(),
        dlq_topic="code-changes-dlq",
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

    yielded = [c async for c in source.listen()]

    assert yielded == []  # poison message is not yielded downstream
    source._dlq_producer.send_and_wait.assert_awaited_once()
    source.consumer.commit.assert_awaited_once()  # advances past the poison message


@pytest.mark.asyncio
async def test_start_and_stop_manage_consumer_and_dlq_producer(mock_kafka):
    source = KafkaCodeChangeSource(
        bootstrap_servers="localhost:9092",
        topic="code-changes",
        group_id="test",
        schema_client=MagicMock(),
        dlq_topic="code-changes-dlq",
    )

    await source.start()
    await source.stop()

    mock_kafka["consumer"].start.assert_awaited_once()
    mock_kafka["dlq_producer"].start.assert_awaited_once()
    mock_kafka["consumer"].stop.assert_awaited_once()
    mock_kafka["dlq_producer"].stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_route_to_dlq_is_noop_when_producer_absent():
    source = KafkaCodeChangeSource(
        bootstrap_servers="localhost:9092",
        topic="code-changes",
        group_id="test",
        schema_client=MagicMock(),
        dlq_topic="code-changes-dlq",
    )

    # No producer started — must not raise.
    await source._route_to_dlq(MagicMock(), ValueError("boom"))


@pytest.mark.asyncio
async def test_route_to_dlq_swallows_publish_failure():
    source = KafkaCodeChangeSource(
        bootstrap_servers="localhost:9092",
        topic="code-changes",
        group_id="test",
        schema_client=MagicMock(),
        dlq_topic="code-changes-dlq",
    )
    source._dlq_producer = AsyncMock()
    source._dlq_producer.send_and_wait.side_effect = RuntimeError("broker down")

    # DLQ publish failure is logged, not propagated.
    await source._route_to_dlq(MagicMock(), ValueError("boom"))
