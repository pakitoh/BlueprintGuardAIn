import asyncio

import pytest

from src.infrastructure.heartbeat import Heartbeat


@pytest.mark.asyncio
async def test_start_creates_file_immediately(tmp_path):
    path = tmp_path / "heartbeat"
    hb = Heartbeat(path=str(path), interval_seconds=0.01)

    await hb.start()
    try:
        assert path.exists()
    finally:
        await hb.stop()


@pytest.mark.asyncio
async def test_touches_repeatedly_on_interval(tmp_path, mocker):
    path = tmp_path / "heartbeat"
    hb = Heartbeat(path=str(path), interval_seconds=0.01)
    spy = mocker.spy(hb, "_touch")

    await hb.start()
    await asyncio.sleep(0.05)
    await hb.stop()

    # one immediate touch on start + at least one from the timer loop
    assert spy.call_count >= 2


@pytest.mark.asyncio
async def test_stop_cancels_the_task(tmp_path):
    path = tmp_path / "heartbeat"
    hb = Heartbeat(path=str(path), interval_seconds=0.01)

    await hb.start()
    task = hb._task
    await hb.stop()

    assert task is not None and task.cancelled()


@pytest.mark.asyncio
async def test_stop_without_start_is_noop(tmp_path):
    hb = Heartbeat(path=str(tmp_path / "heartbeat"), interval_seconds=1.0)
    await hb.stop()  # must not raise
