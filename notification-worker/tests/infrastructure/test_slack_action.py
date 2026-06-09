from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.domain.entities import AnalysisResult
from src.domain.exceptions import ActionError
from src.infrastructure.actions.slack_action import SlackAction


def a_result(status="FAILED", findings=None) -> AnalysisResult:
    return AnalysisResult(
        repository="owner/repo",
        sha="abc123",
        status=status,
        findings=findings if findings is not None else ["finding-1"],
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
        "src.infrastructure.actions.slack_action.httpx.AsyncClient",
        return_value=client,
    )
    return client


@pytest.mark.asyncio
async def test_posts_to_webhook_url(mocker):
    client = _mock_client(mocker)
    action = SlackAction(webhook_url="https://hooks.slack.com/abc")

    await action.execute(a_result())

    assert client.post.call_args.args[0] == "https://hooks.slack.com/abc"


@pytest.mark.asyncio
async def test_message_includes_status_repo_and_findings(mocker):
    client = _mock_client(mocker)
    action = SlackAction(webhook_url="https://hooks.slack.com/abc")

    await action.execute(a_result(status="FAILED", findings=["domain leak"]))

    text = client.post.call_args.kwargs["json"]["text"]
    assert "FAILED" in text
    assert "owner/repo" in text
    assert "domain leak" in text


@pytest.mark.asyncio
async def test_raises_action_error_on_http_failure(mocker):
    _mock_client(mocker, fail=True)
    action = SlackAction(webhook_url="https://hooks.slack.com/abc")

    with pytest.raises(ActionError):
        await action.execute(a_result())
