import asyncpg
import structlog

from src.domain.ports.idempotency_store import IdempotencyStore

logger = structlog.get_logger()


class PgIdempotencyStore(IdempotencyStore):
    """Durable, cross-restart dedup of analysed changes, keyed on
    ``repository@target_sha``.

    Best-effort: storage failures are logged and treated as "not processed" so a
    dedup-store outage degrades to possible duplicate analyses rather than
    blocking the pipeline.
    """

    def __init__(self, dsn: str):
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def start(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn)
        logger.debug("idempotency_pool_created")

    async def stop(self) -> None:
        if self._pool:
            await self._pool.close()
            logger.debug("idempotency_pool_closed")

    async def is_processed(self, key: str) -> bool:
        try:
            row = await self._pool.fetchval(  # type: ignore[union-attr]
                "SELECT 1 FROM processed_changes WHERE change_key = $1", key
            )
            return row is not None
        except Exception as e:
            logger.warning("idempotency_check_failed", error=str(e))
            return False

    async def mark_processed(self, key: str) -> None:
        try:
            await self._pool.execute(  # type: ignore[union-attr]
                "INSERT INTO processed_changes (change_key) VALUES ($1) "
                "ON CONFLICT (change_key) DO NOTHING",
                key,
            )
        except Exception as e:
            logger.warning("idempotency_mark_failed", error=str(e))
