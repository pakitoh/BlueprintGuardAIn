import structlog
import httpx

from src.domain.ports.diff_fetcher import DiffFetcher, FileDiff

logger = structlog.get_logger()


class GitHubDiffFetcher(DiffFetcher):
    _BASE = "https://api.github.com"

    def __init__(self, token: str):
        self._headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    async def fetch(self, repository: str, sha: str) -> list[FileDiff]:
        url = f"{self._BASE}/repos/{repository}/commits/{sha}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers, timeout=10.0)
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
