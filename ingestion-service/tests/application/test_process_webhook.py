import pytest
from unittest.mock import AsyncMock
from src.application.use_cases.process_webhook import ProcessWebhookUseCase
from src.domain.ports.repository import CodeChangeRepository
from src.domain.exceptions import MappingError


@pytest.fixture
def mock_repo():
    return AsyncMock(spec=CodeChangeRepository)


@pytest.fixture
def use_case(mock_repo):
    return ProcessWebhookUseCase(repository=mock_repo)


@pytest.mark.asyncio
async def test_should_process_push_event(use_case, mock_repo):
    payload = {
        "ref": "refs/heads/main",
        "after": "sha123",
        "repository": {"full_name": "paco/repo"},
    }

    await use_case.execute(payload, event_type="push")

    mock_repo.save.assert_called_once()
    saved_change = mock_repo.save.call_args[0][0]
    assert saved_change.repository == "paco/repo"
    assert saved_change.event_type == "push"


@pytest.mark.asyncio
async def test_should_process_pull_request_event(use_case, mock_repo):
    payload = {
        "action": "opened",
        "number": 1,
        "pull_request": {"head": {"sha": "sha456"}},
        "repository": {"full_name": "paco/repo"},
    }

    await use_case.execute(payload, event_type="pull_request")

    mock_repo.save.assert_called_once()
    saved_change = mock_repo.save.call_args[0][0]
    assert saved_change.repository == "paco/repo"
    assert saved_change.event_type == "pull_request"


@pytest.mark.asyncio
async def test_should_raise_error_for_unsupported_event(use_case):
    with pytest.raises(MappingError) as exc:
        await use_case.execute({}, event_type="unsupported")
    assert "Unsupported event type" in str(exc.value)
