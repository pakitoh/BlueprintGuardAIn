from unittest.mock import AsyncMock

import pytest

from src.application.use_cases.trigger_replay import trigger_replay
from tests.conftest import a_record

MOD = "src.application.use_cases.trigger_replay"


@pytest.mark.asyncio
async def test_trigger_replay_fetches_sends_and_records(mocker):
    fetch = mocker.patch(
        f"{MOD}.fetch_next_chronological_commit", return_value=("sha1", "msg")
    )
    send = mocker.patch(f"{MOD}._send_webhook")
    record = a_record()
    create = mocker.patch(f"{MOD}._create_pending_record", return_value=record)
    repo, progress, cache = AsyncMock(), AsyncMock(), {}

    result = await trigger_replay(
        repo_name="octocat/Hello-World",
        repo=repo,
        ingestion_url="http://ingestion",
        github_token="t",
        webhook_secret="s",
        progress_repo=progress,
        page_cache=cache,
    )

    assert result is record
    fetch.assert_awaited_once_with("octocat/Hello-World", "t", progress, cache)
    send.assert_awaited_once_with(
        "octocat/Hello-World", "sha1", "msg", "http://ingestion", "s"
    )
    create.assert_awaited_once_with(repo, "octocat/Hello-World", "sha1")
