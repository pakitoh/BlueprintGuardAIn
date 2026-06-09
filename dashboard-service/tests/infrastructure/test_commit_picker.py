from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.entities import ReplayProgress
from src.infrastructure.github import commit_picker
from src.infrastructure.github.commit_picker import (
    _parse_last_page,
    fetch_commit_diff,
    fetch_next_chronological_commit,
    pick_random_commit,
)

MOD = "src.infrastructure.github.commit_picker"


def _resp(json_data, headers=None):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.headers = headers or {}
    resp.raise_for_status = MagicMock()
    return resp


def _mock_client(mocker, responses):
    client = MagicMock()
    client.get = AsyncMock(side_effect=responses)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    mocker.patch(f"{MOD}.httpx.AsyncClient", return_value=client)
    return client


def test_parse_last_page_extracts_page_number():
    link = '<https://api.github.com/x?page=7>; rel="last"'
    assert _parse_last_page(link) == 7


def test_parse_last_page_returns_none_without_last_rel():
    assert _parse_last_page("") is None


@pytest.mark.asyncio
async def test_fetch_commit_diff_builds_unified_diff(mocker):
    _mock_client(
        mocker,
        [
            _resp(
                {
                    "files": [
                        {"filename": "a.py", "patch": "@@ -1 +1 @@\n-x\n+y"},
                        {"filename": "b.bin", "patch": None},  # skipped (no patch)
                    ]
                }
            )
        ],
    )

    diff = await fetch_commit_diff("octocat/Hello-World", "abc", "token")

    assert "diff --git a/a.py b/a.py" in diff
    assert "b.bin" not in diff


@pytest.mark.asyncio
async def test_pick_random_commit_returns_commit_with_enough_files(mocker):
    mocker.patch.object(commit_picker.random, "choice", return_value="octocat/repo")
    mocker.patch.object(commit_picker.random, "shuffle", side_effect=lambda x: None)
    _mock_client(
        mocker,
        [
            _resp([{"sha": "s1", "commit": {"message": "fix bug\nmore"}}]),
            _resp({"files": [1, 2, 3]}),  # >= MIN_FILES
        ],
    )

    repo, sha, message = await pick_random_commit("token")

    assert (repo, sha, message) == ("octocat/repo", "s1", "fix bug")


@pytest.mark.asyncio
async def test_pick_random_commit_raises_when_no_suitable_commit(mocker):
    mocker.patch.object(commit_picker.random, "choice", return_value="octocat/repo")
    mocker.patch.object(commit_picker.random, "shuffle", side_effect=lambda x: None)
    _mock_client(
        mocker,
        [
            _resp([{"sha": "s1", "commit": {"message": "tiny"}}]),
            _resp({"files": [1]}),  # < MIN_FILES
        ],
    )

    with pytest.raises(RuntimeError, match="No commit with"):
        await pick_random_commit("token")


@pytest.mark.asyncio
async def test_fetch_next_chronological_first_page(mocker):
    progress_repo = AsyncMock()
    progress_repo.get.return_value = None  # no prior progress
    _mock_client(
        mocker,
        [_resp([{"sha": "s1", "commit": {"message": "first\nbody"}}], headers={})],
    )
    cache: dict = {}

    sha, message = await fetch_next_chronological_commit(
        "octocat/repo", "token", progress_repo, cache
    )

    assert (sha, message) == ("s1", "first")
    progress_repo.save.assert_awaited_once()
    saved = progress_repo.save.call_args.args[0]
    assert saved.current_page == 0  # single page exhausted -> moves below 1


@pytest.mark.asyncio
async def test_fetch_next_chronological_raises_when_exhausted(mocker):
    progress_repo = AsyncMock()
    progress_repo.get.return_value = ReplayProgress(
        repository="octocat/repo", last_page=1, current_page=0, page_index=0
    )
    _mock_client(mocker, [])

    with pytest.raises(RuntimeError, match="have been replayed"):
        await fetch_next_chronological_commit(
            "octocat/repo", "token", progress_repo, {}
        )
