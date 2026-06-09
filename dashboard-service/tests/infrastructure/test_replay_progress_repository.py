from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.entities import ReplayProgress
from src.infrastructure.postgres.replay_progress_repository import (
    PostgresReplayProgressRepository,
)


def _conn() -> MagicMock:
    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.fetchrow = AsyncMock()
    return conn


def _pool(conn: MagicMock) -> MagicMock:
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool


@pytest.fixture
def conn() -> MagicMock:
    return _conn()


@pytest.fixture
def repo(conn) -> PostgresReplayProgressRepository:
    repository = PostgresReplayProgressRepository(dsn="postgresql://x")
    repository._pool = _pool(conn)
    return repository


@pytest.mark.asyncio
async def test_get_returns_progress(repo, conn):
    conn.fetchrow.return_value = {
        "repository": "octocat/Hello-World",
        "last_page": 5,
        "current_page": 3,
        "page_index": 2,
    }

    progress = await repo.get("octocat/Hello-World")

    assert progress == ReplayProgress(
        repository="octocat/Hello-World", last_page=5, current_page=3, page_index=2
    )


@pytest.mark.asyncio
async def test_get_returns_none_when_missing(repo, conn):
    conn.fetchrow.return_value = None

    assert await repo.get("octocat/Hello-World") is None


@pytest.mark.asyncio
async def test_save_upserts_progress(repo, conn):
    await repo.save(
        ReplayProgress(
            repository="octocat/Hello-World",
            last_page=5,
            current_page=3,
            page_index=2,
        )
    )

    sql = conn.execute.call_args.args[0]
    assert "INSERT INTO replay_progress" in sql
    assert "ON CONFLICT (repository) DO UPDATE" in sql
