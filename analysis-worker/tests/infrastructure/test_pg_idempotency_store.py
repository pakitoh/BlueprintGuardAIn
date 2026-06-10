from unittest.mock import AsyncMock

import pytest

from src.infrastructure.postgres.idempotency_store import PgIdempotencyStore


def a_store(pool=None) -> PgIdempotencyStore:
    store = PgIdempotencyStore(dsn="postgresql://unused")
    store._pool = pool or AsyncMock()
    return store


@pytest.mark.asyncio
async def test_is_processed_true_when_row_exists():
    pool = AsyncMock()
    pool.fetchval = AsyncMock(return_value=1)
    store = a_store(pool)

    assert await store.is_processed("org/x@s1") is True
    pool.fetchval.assert_awaited_once()
    assert pool.fetchval.call_args[0][1] == "org/x@s1"


@pytest.mark.asyncio
async def test_is_processed_false_when_no_row():
    pool = AsyncMock()
    pool.fetchval = AsyncMock(return_value=None)

    assert await a_store(pool).is_processed("org/x@s1") is False


@pytest.mark.asyncio
async def test_is_processed_returns_false_and_swallows_db_error():
    pool = AsyncMock()
    pool.fetchval = AsyncMock(side_effect=Exception("db down"))

    # A dedup-store outage must not block the pipeline.
    assert await a_store(pool).is_processed("org/x@s1") is False


@pytest.mark.asyncio
async def test_mark_processed_inserts_with_on_conflict_do_nothing():
    pool = AsyncMock()
    pool.execute = AsyncMock()

    await a_store(pool).mark_processed("org/x@s1")

    sql, key = pool.execute.call_args[0]
    assert "INSERT INTO processed_changes" in sql
    assert "ON CONFLICT (change_key) DO NOTHING" in sql
    assert key == "org/x@s1"


@pytest.mark.asyncio
async def test_mark_processed_swallows_db_error():
    pool = AsyncMock()
    pool.execute = AsyncMock(side_effect=Exception("db down"))

    # Must not raise.
    await a_store(pool).mark_processed("org/x@s1")


@pytest.mark.asyncio
async def test_start_creates_pool_and_stop_closes_it(mocker):
    pool = AsyncMock()
    pool.close = AsyncMock()
    mocker.patch(
        "src.infrastructure.postgres.idempotency_store.asyncpg.create_pool",
        new_callable=AsyncMock,
        return_value=pool,
    )
    store = PgIdempotencyStore(dsn="postgresql://x")

    await store.start()
    await store.stop()

    pool.close.assert_awaited_once()
