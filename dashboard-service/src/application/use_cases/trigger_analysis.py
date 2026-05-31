import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime

import httpx
import structlog

from src.domain.entities import AnalysisRecord
from src.domain.ports.analysis_repository import AnalysisRepository
from src.infrastructure.github.commit_picker import pick_random_commit

logger = structlog.get_logger()


async def trigger_analysis(
    repo: AnalysisRepository,
    ingestion_url: str,
    github_token: str,
    webhook_secret: str,
) -> AnalysisRecord:
    repository, sha, message = await pick_random_commit(github_token)
    await _send_webhook(repository, sha, message, ingestion_url, webhook_secret)
    record = await _create_pending_record(repo, repository, sha)
    return record


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def _send_webhook(
    repository: str, sha: str, message: str, ingestion_url: str, webhook_secret: str
) -> None:
    payload = {
        "ref": "refs/heads/main",
        "after": sha,
        "repository": {
            "full_name": repository,
            "html_url": f"https://github.com/{repository}",
        },
        "commits": [
            {"id": sha, "message": message, "added": [], "modified": [], "removed": []}
        ],
    }
    # Serialize once and send the exact bytes we signed; ingestion-service verifies
    # the HMAC over the raw request body, so re-serialization must be avoided.
    body = json.dumps(payload).encode()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            ingestion_url,
            content=body,
            headers={
                "X-GitHub-Event": "push",
                "Content-Type": "application/json",
                "X-Hub-Signature-256": _sign(body, webhook_secret),
            },
            timeout=5.0,
        )
        resp.raise_for_status()


async def _create_pending_record(
    repo: AnalysisRepository, repository: str, sha: str
) -> AnalysisRecord:
    record = AnalysisRecord(
        id=str(uuid.uuid4()),
        repository=repository,
        sha=sha,
        status="PENDING",
        created_at=datetime.now(UTC),
    )
    await repo.save(record)
    logger.info("analysis_triggered", id=record.id, repo=repository, sha=sha[:7])
    return record
