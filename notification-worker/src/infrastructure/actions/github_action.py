import httpx
import structlog

from src.domain.entities import AnalysisResult
from src.domain.exceptions import ActionError
from src.domain.ports.action_port import ActionPort

logger = structlog.get_logger()


class GitHubAction(ActionPort):
    def __init__(self, token: str, api_url: str):
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self._api_url = api_url.rstrip("/")

    async def execute(self, result: AnalysisResult) -> None:
        url = f"{self._api_url}/repos/{result.repository}/commits/{result.sha}/comments"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json={"body": self._format_comment(result)},
                    headers=self._headers,
                )
                response.raise_for_status()
            logger.info("github_comment_posted", repo=result.repository, sha=result.sha)
        except Exception as e:
            raise ActionError(f"Failed to post GitHub comment: {e}") from e

    def _format_comment(self, result: AnalysisResult) -> str:
        lines = [f"## Blueprint GuardAIn — {result.status}", ""]
        lines.extend(f"- {finding}" for finding in result.findings)
        return "\n".join(lines)
