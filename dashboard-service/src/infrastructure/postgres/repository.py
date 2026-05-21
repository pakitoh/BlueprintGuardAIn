import asyncpg
import structlog

from src.domain.entities import AnalysisRecord
from src.domain.ports.analysis_repository import AnalysisRepository

logger = structlog.get_logger()

_FETCH_QUERY = """
    SELECT r.id, r.repository, r.sha, r.status, r.created_at, r.completed_at,
           COALESCE(array_agg(f.content ORDER BY f.position)
                    FILTER (WHERE f.id IS NOT NULL), ARRAY[]::TEXT[]) AS findings
    FROM analysis_records r
    LEFT JOIN analysis_findings f ON f.analysis_id = r.id
"""


class PostgresAnalysisRepository(AnalysisRepository):
    def __init__(self, dsn: str):
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def start(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn)
        logger.debug("postgres_pool_created")

    async def stop(self) -> None:
        if self._pool:
            await self._pool.close()

    async def save(self, record: AnalysisRecord) -> None:
        async with self._pool.acquire() as conn:
            await self._insert_record(conn, record)

    async def update(self, record: AnalysisRecord) -> None:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await self._update_record_status(conn, record)
                await self._insert_findings(conn, record)

    async def get(self, id: str) -> AnalysisRecord | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                _FETCH_QUERY + "WHERE r.id = $1 GROUP BY r.id", id
            )
        return _to_entity(row) if row else None

    async def get_by_repo_sha(self, repository: str, sha: str) -> AnalysisRecord | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                _FETCH_QUERY
                + "WHERE r.repository = $1 AND r.sha = $2 GROUP BY r.id LIMIT 1",
                repository,
                sha,
            )
        return _to_entity(row) if row else None

    async def list_all(self) -> list[AnalysisRecord]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                _FETCH_QUERY + "GROUP BY r.id ORDER BY r.created_at DESC"
            )
        return [_to_entity(r) for r in rows]

    async def _insert_record(
        self, conn: asyncpg.Connection, record: AnalysisRecord
    ) -> None:
        await conn.execute(
            "INSERT INTO analysis_records (id, repository, sha, status, created_at) VALUES ($1,$2,$3,$4,$5)",
            record.id,
            record.repository,
            record.sha,
            record.status,
            record.created_at,
        )

    async def _update_record_status(
        self, conn: asyncpg.Connection, record: AnalysisRecord
    ) -> None:
        await conn.execute(
            "UPDATE analysis_records SET status=$1, completed_at=$2 WHERE id=$3",
            record.status,
            record.completed_at,
            record.id,
        )

    async def _insert_findings(
        self, conn: asyncpg.Connection, record: AnalysisRecord
    ) -> None:
        if record.findings:
            await conn.executemany(
                "INSERT INTO analysis_findings (analysis_id, position, content) VALUES ($1,$2,$3)",
                [(record.id, i, finding) for i, finding in enumerate(record.findings)],
            )


def _to_entity(row: asyncpg.Record) -> AnalysisRecord:
    return AnalysisRecord(
        id=row["id"],
        repository=row["repository"],
        sha=row["sha"],
        status=row["status"],
        findings=list(row["findings"]),
        created_at=row["created_at"],
        completed_at=row["completed_at"],
    )
