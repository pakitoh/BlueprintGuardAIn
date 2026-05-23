from typing import Any

import httpx
import structlog
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from src.domain.ports.diff_fetcher import DiffFetcher, FileDiff
from src.infrastructure.github.github_config import (
    GITHUB_MAX_ATTEMPTS,
    GITHUB_TIMEOUT,
    GITHUB_WAIT_MAX,
    GITHUB_WAIT_MIN,
    GITHUB_WAIT_MULTIPLIER,
)

logger = structlog.get_logger()


def _log_github_retry(rs: RetryCallState) -> None:
    err: Any = rs.outcome.exception() if rs.outcome is not None else None
    logger.warning("github_retry", attempt=rs.attempt_number, error=str(err))


def _is_retryable_github_error(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return False


class GitHubDiffFetcher(DiffFetcher):
    _BASE = "https://api.github.com"

    def __init__(self, token: str):
        self._headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    @retry(
        stop=stop_after_attempt(GITHUB_MAX_ATTEMPTS),
        wait=wait_exponential(
            multiplier=GITHUB_WAIT_MULTIPLIER, min=GITHUB_WAIT_MIN, max=GITHUB_WAIT_MAX
        ),
        retry=retry_if_exception(_is_retryable_github_error),
        reraise=True,
        before_sleep=_log_github_retry,
    )
    async def fetch(self, repository: str, sha: str) -> list[FileDiff]:
        try:
            url = f"{self._BASE}/repos/{repository}/commits/{sha}"
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url,
                    headers=self._headers,
                    timeout=GITHUB_TIMEOUT,
                    follow_redirects=True,
                )
                resp.raise_for_status()
            logger.debug(
                "github_diff_fetched",
                repository=repository,
                sha=sha,
                files=len(resp.json().get("files", [])),
            )
            return [
                FileDiff(
                    filename=f["filename"],
                    status=f["status"],
                    patch=f.get("patch", ""),
                )
                for f in resp.json().get("files", [])
            ]
        except Exception as e:
            logger.warning(
                "diff_fetch_failed", repository=repository, sha=sha, error=str(e)
            )
            return []
