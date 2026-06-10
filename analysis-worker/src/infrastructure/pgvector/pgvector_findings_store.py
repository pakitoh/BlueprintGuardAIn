import time

import asyncpg
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from src.domain.entities import CodeChange, PastFinding
from src.domain.ports.diff_fetcher import FileDiff
from src.domain.ports.embedder import Embedder
from src.domain.ports.findings_store import FindingsStore
from src.infrastructure.metrics import rag_retrieval_duration, rag_similar_count
from src.infrastructure.pgvector.pgvector_config import (
    EMBED_MAX_ATTEMPTS,
    EMBED_WAIT_MAX,
    EMBED_WAIT_MIN,
    EMBED_WAIT_MULTIPLIER,
    SIMILARITY_MAX_DISTANCE,
)
from src.infrastructure.retry_logging import make_retry_logger

logger = structlog.get_logger()


_LAYER_KEYWORDS = {
    "domain",
    "application",
    "infrastructure",
    "interface",
    "use_cases",
    "ports",
    "kafka",
    "llm",
    "pgvector",
    "api",
}


def _to_embedding_text(
    change: CodeChange, file_diffs: list[FileDiff] | None = None
) -> str:
    """Produce a repo-agnostic text for similarity search."""
    if file_diffs:
        parts = [f"{fd.filename}:\n{fd.patch[:500]}" for fd in file_diffs if fd.patch]
        if parts:
            return "\n".join(parts)

    # fallback to path-based text when no diffs are available
    commits = change.raw_payload.get("commits", [])

    normalized_paths: list[str] = []
    messages: list[str] = []

    for commit in commits:
        for path in (
            commit.get("added", [])
            + commit.get("modified", [])
            + commit.get("removed", [])
        ):
            parts = path.replace("\\", "/").split("/")
            layer_parts = [p for p in parts[:-1] if p.lower() in _LAYER_KEYWORDS]
            normalized_paths.append("/".join([*layer_parts, parts[-1]]))

        if msg := commit.get("message", "").strip():
            messages.append(msg)

    lines = []
    if normalized_paths:
        lines.append("Changed files: " + ", ".join(normalized_paths))
    if messages:
        lines.append("Commit messages: " + "; ".join(messages))
    return "\n".join(lines) or f"event={change.event_type} ref={change.ref}"


def _to_vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(str(v) for v in vector) + "]"


class PgVectorFindingsStore(FindingsStore):
    def __init__(
        self,
        dsn: str,
        embedder: Embedder,
        max_distance: float = SIMILARITY_MAX_DISTANCE,
    ):
        self._dsn = dsn
        self._embedder = embedder
        self._max_distance = max_distance
        self._pool: asyncpg.Pool | None = None

    @retry(
        stop=stop_after_attempt(EMBED_MAX_ATTEMPTS),
        wait=wait_exponential(
            multiplier=EMBED_WAIT_MULTIPLIER, min=EMBED_WAIT_MIN, max=EMBED_WAIT_MAX
        ),
        reraise=True,
        before_sleep=make_retry_logger("embed_retry"),
    )
    async def _embed(self, text: str) -> list[float]:
        return await self._embedder.embed(text)

    async def start(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn)
        logger.debug("pgvector_pool_created")

    async def stop(self) -> None:
        if self._pool:
            await self._pool.close()
            logger.debug("pgvector_pool_closed")

    async def _embed_change(
        self, change: CodeChange, file_diffs: list[FileDiff] | None
    ) -> tuple[str, str]:
        text = _to_embedding_text(change, file_diffs)
        vector = await self._embed(text)
        return text, _to_vector_literal(vector)

    async def find_similar(
        self,
        change: CodeChange,
        limit: int = 3,
        file_diffs: list[FileDiff] | None = None,
    ) -> list[PastFinding]:
        try:
            _, vector_literal = await self._embed_change(change, file_diffs)
            return await self._query_similar(vector_literal, limit)
        except Exception as e:
            logger.warning("findings_store_unavailable", error=str(e))
            return []

    async def _query_similar(
        self, vector_literal: str, limit: int
    ) -> list[PastFinding]:
        start = time.perf_counter()
        rows = await self._pool.fetch(  # type: ignore[union-attr]
            """
            SELECT rule_text, context
            FROM   past_findings
            WHERE  embedding <=> $1::vector < $2
            ORDER  BY embedding <=> $1::vector
            LIMIT  $3
            """,
            vector_literal,
            self._max_distance,
            limit,
        )
        rag_retrieval_duration.record(time.perf_counter() - start)
        findings = [
            PastFinding(rule_text=r["rule_text"], context=r["context"]) for r in rows
        ]
        rag_similar_count.record(len(findings))
        if findings:
            logger.info(
                "rag_examples_found",
                count=len(findings),
                rules=[f.rule_text for f in findings],
            )
        return findings

    async def save(
        self,
        change: CodeChange,
        findings: list[str],
        file_diffs: list[FileDiff] | None = None,
    ) -> None:
        if not findings:
            return
        try:
            text, vector_literal = await self._embed_change(change, file_diffs)
            await self._insert_finding(change, findings, text, vector_literal)
        except Exception as e:
            logger.warning("findings_save_failed", error=str(e))

    async def _insert_finding(
        self,
        change: CodeChange,
        findings: list[str],
        text: str,
        vector_literal: str,
    ) -> None:
        combined = "\n".join(findings)
        await self._pool.execute(  # type: ignore[union-attr]
            """
            INSERT INTO past_findings (rule_text, context, embedding)
            VALUES ($1, $2, $3::vector)
            """,
            combined,
            text,
            vector_literal,
        )
        logger.debug("past_finding_saved", repository=change.repository)
