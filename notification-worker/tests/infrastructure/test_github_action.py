from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.domain.entities import AnalysisResult
from src.domain.exceptions import ActionError
from src.infrastructure.actions.github_action import GitHubAction


def a_result(status="COMPLETED", findings=None) -> AnalysisResult:
    return AnalysisResult(
        repository="owner/repo",
        sha="abc123",
        status=status,
        findings=findings if findings is not None else ["finding-1", "finding-2"],
        timestamp="2026-01-01T00:00:00Z",
    )


def _mock_client(mocker, *, fail=False):
    error = httpx.HTTPStatusError("boom", request=MagicMock(), response=MagicMock())
    response = MagicMock()
    response.raise_for_status = MagicMock(side_effect=error if fail else None)
    client = MagicMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    mocker.patch(
        "src.infrastructure.actions.github_action.httpx.AsyncClient",
        return_value=client,
    )
    return client


@pytest.mark.asyncio
async def test_posts_comment_to_commit_endpoint(mocker):
    client = _mock_client(mocker)
    action = GitHubAction(token="t0ken", api_url="https://api.github.com")

    await action.execute(a_result())

    url = client.post.call_args.args[0]
    assert url == "https://api.github.com/repos/owner/repo/commits/abc123/comments"


@pytest.mark.asyncio
async def test_sends_bearer_token_and_findings_in_body(mocker):
    client = _mock_client(mocker)
    action = GitHubAction(token="t0ken", api_url="https://api.github.com")

    await action.execute(a_result(findings=["use ports", "no domain leak"]))

    kwargs = client.post.call_args.kwargs
    assert kwargs["headers"]["Authorization"] == "Bearer t0ken"
    body = kwargs["json"]["body"]
    assert "- use ports" in body
    assert "- no domain leak" in body


@pytest.mark.asyncio
async def test_strips_trailing_slash_from_api_url(mocker):
    client = _mock_client(mocker)
    action = GitHubAction(token="t0ken", api_url="https://api.github.com/")

    await action.execute(a_result())

    assert client.post.call_args.args[0].startswith("https://api.github.com/repos/")


@pytest.mark.asyncio
async def test_raises_action_error_on_http_failure(mocker):
    _mock_client(mocker, fail=True)
    action = GitHubAction(token="t0ken", api_url="https://api.github.com")

    with pytest.raises(ActionError):
        await action.execute(a_result())
