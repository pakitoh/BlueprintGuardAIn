from src.application.use_cases.trigger_analysis import (
    _create_pending_record,
    _send_webhook,
)
from src.domain.entities import AnalysisRecord
from src.domain.ports.analysis_repository import AnalysisRepository
from src.domain.ports.replay_progress_repository import ReplayProgressRepository
from src.infrastructure.github.commit_picker import fetch_next_chronological_commit


async def trigger_replay(
    repo_name: str,
    repo: AnalysisRepository,
    ingestion_url: str,
    github_token: str,
    webhook_secret: str,
    progress_repo: ReplayProgressRepository,
    page_cache: dict,
) -> AnalysisRecord:
    sha, message = await fetch_next_chronological_commit(
        repo_name, github_token, progress_repo, page_cache
    )
    await _send_webhook(repo_name, sha, message, ingestion_url, webhook_secret)
    return await _create_pending_record(repo, repo_name, sha)
