import os
import re
import structlog
from typing import List

import asyncpg

from src.domain.entities import CodeChange, PastFinding
from src.domain.ports.embedder import Embedder
from src.domain.ports.findings_store import FindingsStore

logger = structlog.get_logger()

_LAYER_KEYWORDS = {
    "domain", "application", "infrastructure", "interface",
    "use_cases", "ports", "kafka", "llm", "pgvector", "api",
}


def _to_embedding_text(change: CodeChange) -> str:
    """Produce a repo-agnostic text for similarity search."""
    commits = change.raw_payload.get("commits", [])

    normalized_paths: List[str] = []
    messages: List[str] = []

    for commit in commits:
        for path in commit.get("added", []) + commit.get("modified", []) + commit.get("removed", []):
            parts = path.replace("\\", "/").split("/")
            # keep file name + any recognised layer segments
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

    async def find_similar(self, change: CodeChange, limit: int = 3) -> List[PastFinding]:
        text = _to_embedding_text(change)
        vector = await self._embedder.embed(text)
        vector_literal = "[" + ",".join(str(v) for v in vector) + "]"

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
        return [PastFinding(rule_text=r["rule_text"], context=r["context"]) for r in rows]

    async def save(self, change: CodeChange, findings: List[str]) -> None:
        if not findings:
            return
        text = _to_embedding_text(change)
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
