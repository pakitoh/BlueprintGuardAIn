import hashlib
import hmac
from unittest.mock import AsyncMock, patch

import pytest

from src.application.use_cases.trigger_analysis import trigger_analysis


@pytest.mark.asyncio
@patch("src.application.use_cases.trigger_analysis.pick_random_commit")
@patch("src.application.use_cases.trigger_analysis.httpx.AsyncClient")
async def test_trigger_analysis_signs_the_exact_body(mock_client_class, mock_pick):
    mock_pick.return_value = ("octocat/Hello-World", "abc123", "Initial commit")
    mock_repo = AsyncMock()
    mock_client = AsyncMock()
    mock_client.post.return_value.raise_for_status = lambda: None
    mock_client_class.return_value.__aenter__.return_value = mock_client

    await trigger_analysis(
        repo=mock_repo,
        ingestion_url="http://ingestion/webhooks/github",
        github_token="token123",
        webhook_secret="s3cret",
    )

    _args, kwargs = mock_client.post.call_args
    sent_body = kwargs["content"]
    # the signature must be computed over the exact bytes that are sent
    expected = "sha256=" + hmac.new(b"s3cret", sent_body, hashlib.sha256).hexdigest()
    assert kwargs["headers"]["X-Hub-Signature-256"] == expected
    assert kwargs["headers"]["X-GitHub-Event"] == "push"
    mock_repo.save.assert_awaited_once()
