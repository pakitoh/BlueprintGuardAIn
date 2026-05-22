from src.domain.entities import AnalysisRecord
from src.domain.ports.analysis_repository import AnalysisRepository
from src.domain.ports.replay_progress_repository import ReplayProgressRepository
from src.infrastructure.github.commit_picker import fetch_next_chronological_commit
from src.application.use_cases.trigger_analysis import _send_webhook, _create_pending_record


async def trigger_replay(
    repo_name: str,
    repo: AnalysisRepository,
    ingestion_url: str,
    github_token: str,
    progress_repo: ReplayProgressRepository,
    page_cache: dict,
) -> AnalysisRecord:
    sha, message = await fetch_next_chronological_commit(
        repo_name, github_token, progress_repo, page_cache
    )
    await _send_webhook(repo_name, sha, message, ingestion_url)
    return await _create_pending_record(repo, repo_name, sha)
