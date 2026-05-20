import uuid
import httpx
import structlog
from datetime import datetime

from src.domain.entities import AnalysisRecord
from src.infrastructure.github.commit_picker import pick_random_commit

logger = structlog.get_logger()


async def trigger_analysis(
    store: dict[str, AnalysisRecord],
    ingestion_url: str,
    github_token: str,
) -> AnalysisRecord:
    repo, sha, message = await pick_random_commit(github_token)

    payload = {
        "ref": "refs/heads/main",
        "after": sha,
        "repository": {"full_name": repo, "html_url": f"https://github.com/{repo}"},
        "commits": [
            {"id": sha, "message": message, "added": [], "modified": [], "removed": []}
        ],
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            ingestion_url,
            json=payload,
            headers={"X-GitHub-Event": "push"},
            timeout=5.0,
        )
        resp.raise_for_status()

    record = AnalysisRecord(
        id=str(uuid.uuid4()),
        repository=repo,
        sha=sha,
        status="PENDING",
        created_at=datetime.utcnow(),
    )
    store[record.id] = record
    logger.info("analysis_triggered", id=record.id, repo=repo, sha=sha[:7])
    return record
