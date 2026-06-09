from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.postgres.repository import (
    PostgresAnalysisRepository,
    _to_entity,
)
from tests.conftest import a_record


def _conn() -> MagicMock:
    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.executemany = AsyncMock()
    conn.fetchrow = AsyncMock()
    conn.fetch = AsyncMock()
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)
    return conn


def _pool(conn: MagicMock) -> MagicMock:
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_cm)
    pool.close = AsyncMock()
    return pool


def _row(**overrides):
    row = {
        "id": "rec-1",
        "repository": "octocat/Hello-World",
        "sha": "abc123",
        "status": "COMPLETED",
        "findings": ["f1", "f2"],
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "completed_at": datetime(2026, 1, 2, tzinfo=UTC),
    }
    row.update(overrides)
    return row


@pytest.fixture
def conn() -> MagicMock:
    return _conn()


@pytest.fixture
def repo(conn) -> PostgresAnalysisRepository:
    repository = PostgresAnalysisRepository(dsn="postgresql://x")
    repository._pool = _pool(conn)
    return repository


@pytest.mark.asyncio
async def test_save_inserts_record(repo, conn):
    await repo.save(a_record())

    assert "INSERT INTO analysis_records" in conn.execute.call_args.args[0]


@pytest.mark.asyncio
async def test_update_writes_status_and_findings(repo, conn):
    await repo.update(a_record(status="COMPLETED", findings=["f1", "f2"]))

    assert conn.execute.call_args.args[0].startswith("UPDATE analysis_records")
    conn.executemany.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_skips_findings_when_empty(repo, conn):
    await repo.update(a_record(status="COMPLETED", findings=[]))

    conn.executemany.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_returns_entity(repo, conn):
    conn.fetchrow.return_value = _row()

    record = await repo.get("rec-1")

    assert record is not None
    assert record.id == "rec-1"
    assert record.findings == ["f1", "f2"]


@pytest.mark.asyncio
async def test_get_returns_none_when_missing(repo, conn):
    conn.fetchrow.return_value = None

    assert await repo.get("missing") is None


@pytest.mark.asyncio
async def test_get_by_repo_sha_returns_entity(repo, conn):
    conn.fetchrow.return_value = _row()

    record = await repo.get_by_repo_sha("octocat/Hello-World", "abc123")

    assert record is not None
    assert record.sha == "abc123"


@pytest.mark.asyncio
async def test_list_all_maps_rows(repo, conn):
    conn.fetch.return_value = [_row(id="a"), _row(id="b")]

    records = await repo.list_all()

    assert [r.id for r in records] == ["a", "b"]


@pytest.mark.asyncio
async def test_start_creates_pool_and_stop_closes_it(mocker):
    pool = _pool(_conn())
    mocker.patch(
        "src.infrastructure.postgres.repository.asyncpg.create_pool",
        new_callable=AsyncMock,
        return_value=pool,
    )
    repository = PostgresAnalysisRepository(dsn="postgresql://x")

    await repository.start()
    await repository.stop()

    pool.close.assert_awaited_once()


def test_to_entity_maps_all_fields():
    record = _to_entity(_row())

    assert record.repository == "octocat/Hello-World"
    assert record.completed_at == datetime(2026, 1, 2, tzinfo=UTC)
