import asyncpg
import structlog

from src.domain.entities import ReplayProgress
from src.domain.ports.replay_progress_repository import ReplayProgressRepository

logger = structlog.get_logger()


class PostgresReplayProgressRepository(ReplayProgressRepository):
    def __init__(self, dsn: str):
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def start(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn)
        logger.debug("replay_progress_pool_created")

    async def stop(self) -> None:
        if self._pool:
            await self._pool.close()

    async def get(self, repository: str) -> ReplayProgress | None:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM replay_progress WHERE repository = $1", repository
            )
        if not row:
            return None
        return ReplayProgress(
            repository=row["repository"],
            last_page=row["last_page"],
            current_page=row["current_page"],
            page_index=row["page_index"],
        )

    async def save(self, progress: ReplayProgress) -> None:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO replay_progress
                    (repository, last_page, current_page, page_index)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (repository) DO UPDATE
                SET last_page = $2, current_page = $3, page_index = $4
                """,
                progress.repository,
                progress.last_page,
                progress.current_page,
                progress.page_index,
            )
