import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock

from src.infrastructure.github.github_diff_fetcher import GitHubDiffFetcher


def a_fetcher():
    return GitHubDiffFetcher(token="test-token")


def a_github_response(files: list[dict]) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"files": files}
    return resp


@pytest.mark.asyncio
async def test_fetch_returns_file_diffs(mocker):
    files = [{"filename": "src/main.py", "status": "modified", "patch": "+ new line"}]
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value.get = AsyncMock(
        return_value=a_github_response(files)
    )
    mocker.patch(
        "src.infrastructure.github.github_diff_fetcher.httpx.AsyncClient",
        return_value=mock_client,
    )

    result = await a_fetcher().fetch("org/repo", "abc123")

    assert len(result) == 1
    assert result[0].filename == "src/main.py"
    assert result[0].status == "modified"
    assert result[0].patch == "+ new line"


@pytest.mark.asyncio
async def test_fetch_returns_empty_list_on_error(mocker):
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value.get = AsyncMock(
        side_effect=httpx.NetworkError("connection refused")
    )
    mocker.patch(
        "src.infrastructure.github.github_diff_fetcher.httpx.AsyncClient",
        return_value=mock_client,
    )

    result = await a_fetcher().fetch("org/repo", "abc123")

    assert result == []
