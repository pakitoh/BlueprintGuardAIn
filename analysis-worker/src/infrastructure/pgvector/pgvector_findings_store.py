import time
import structlog
from typing import List

import asyncpg

from src.domain.entities import CodeChange, PastFinding
from src.domain.ports.diff_fetcher import FileDiff
from src.domain.ports.embedder import Embedder
from src.domain.ports.findings_store import FindingsStore
from src.infrastructure.metrics import rag_retrieval_duration, rag_similar_count

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

    normalized_paths: List[str] = []
    messages: List[str] = []

    for commit in commits:
        for path in (
            commit.get("added", [])
            + commit.get("modified", [])
            + commit.get("removed", [])
        ):
            parts = path.replace("\\", "/").split("/")
            layer_parts = [p for p in parts[:-1] if p.lower() in _LAYER_KEYWORDS]
            normalized_paths.append("/".join(layer_parts + [parts[-1]]))

        if msg := commit.get("message", "").strip():
            messages.append(msg)

    lines = []
    if normalized_paths:
        lines.append("Changed files: " + ", ".join(normalized_paths))
    if messages:
        lines.append("Commit messages: " + "; ".join(messages))
    return "\n".join(lines) or f"event={change.event_type} ref={change.ref}"


class PgVectorFindingsStore(FindingsStore):
    def __init__(self, dsn: str, embedder: Embedder):
        self._dsn = dsn
        self._embedder = embedder
        self._pool: asyncpg.Pool | None = None

    async def start(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn)
        logger.debug("pgvector_pool_created")

    async def stop(self) -> None:
        if self._pool:
            await self._pool.close()
            logger.debug("pgvector_pool_closed")

    async def find_similar(
        self,
        change: CodeChange,
        limit: int = 3,
        file_diffs: list[FileDiff] | None = None,
    ) -> List[PastFinding]:
        text = _to_embedding_text(change, file_diffs)
        vector = await self._embedder.embed(text)
        vector_literal = "[" + ",".join(str(v) for v in vector) + "]"

        start = time.perf_counter()
        rows = await self._pool.fetch(  # type: ignore[union-attr]
            """
            SELECT rule_text, context
            FROM   past_findings
            ORDER  BY embedding <=> $1::vector
            LIMIT  $2
            """,
            vector_literal,
            limit,
        )
        rag_retrieval_duration.record(time.perf_counter() - start)
        findings = [
            PastFinding(rule_text=r["rule_text"], context=r["context"]) for r in rows
        ]
        rag_similar_count.record(len(findings))
        return findings

    async def save(
        self,
        change: CodeChange,
        findings: List[str],
        file_diffs: list[FileDiff] | None = None,
    ) -> None:
        if not findings:
            return
        text = _to_embedding_text(change, file_diffs)
        vector = await self._embedder.embed(text)
        vector_literal = "[" + ",".join(str(v) for v in vector) + "]"

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
