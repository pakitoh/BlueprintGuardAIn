import asyncio
import struct
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.kafka.result_consumer import KafkaResultConsumer
from tests.conftest import a_record

MOD = "src.infrastructure.kafka.result_consumer"


def _consumer() -> KafkaResultConsumer:
    return KafkaResultConsumer(
        bootstrap_servers="localhost:9092",
        topic="analysis-results",
        group_id="dashboard",
        schema_client=MagicMock(),
    )


def test_deserialize_returns_decoded_dict(mocker):
    consumer = _consumer()
    consumer._schema_client.get_by_id.return_value = MagicMock(
        schema={"type": "record"}
    )
    mocker.patch(
        f"{MOD}.schemaless_reader", return_value={"repository": "r", "sha": "s"}
    )
    payload = struct.pack(">bi", 0, 7) + b"avro-bytes"

    assert consumer._deserialize(payload) == {"repository": "r", "sha": "s"}


def test_deserialize_raises_when_schema_missing():
    consumer = _consumer()
    consumer._schema_client.get_by_id.return_value = None
    payload = struct.pack(">bi", 0, 7) + b"x"

    with pytest.raises(RuntimeError, match="not found"):
        consumer._deserialize(payload)


@pytest.mark.asyncio
async def test_process_message_updates_existing_record(mocker):
    consumer = _consumer()
    repo = AsyncMock()
    repo.get_by_repo_sha.return_value = a_record()
    mocker.patch.object(
        consumer,
        "_deserialize",
        return_value={
            "repository": "r",
            "sha": "s",
            "status": "COMPLETED",
            "findings": ["f"],
        },
    )

    await consumer._process_message(MagicMock(), repo)

    repo.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_message_skips_when_record_missing(mocker):
    consumer = _consumer()
    repo = AsyncMock()
    repo.get_by_repo_sha.return_value = None
    mocker.patch.object(
        consumer, "_deserialize", return_value={"repository": "r", "sha": "s"}
    )

    await consumer._process_message(MagicMock(), repo)

    repo.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_result_updates_record_and_notifies_subscriber():
    consumer = _consumer()
    on_result = AsyncMock()
    consumer._on_result = on_result
    repo = AsyncMock()
    data = {"status": "COMPLETED", "findings": ["f1", "f2"]}

    await consumer._apply_result(repo, a_record(), data)

    updated = repo.update.call_args.args[0]
    assert updated.status == "COMPLETED"
    assert updated.findings == ["f1", "f2"]
    assert updated.completed_at is not None
    on_result.assert_awaited_once_with(updated)


@pytest.mark.asyncio
async def test_consume_logs_and_continues_on_error(mocker):
    consumer = _consumer()

    class _FakeConsumer:
        def __aiter__(self):
            async def gen():
                yield MagicMock()

            return gen()

    consumer._consumer = _FakeConsumer()
    mocker.patch.object(
        consumer, "_process_message", new=AsyncMock(side_effect=RuntimeError("boom"))
    )

    # The error is logged, not propagated.
    await consumer._consume(AsyncMock())


@pytest.mark.asyncio
async def test_start_launches_consume_task_and_stop_cancels_it(mocker):
    consumer = _consumer()

    class _FakeConsumer:
        start = AsyncMock()
        stop = AsyncMock()

        def __aiter__(self):
            async def gen():
                if False:  # never yields; keeps the task short-lived
                    yield None

            return gen()

    fake = _FakeConsumer()
    mocker.patch(f"{MOD}.AIOKafkaConsumer", return_value=fake)

    await consumer.start(repo=AsyncMock())
    await asyncio.sleep(0)
    await consumer.stop()

    fake.start.assert_awaited_once()
    fake.stop.assert_awaited_once()
