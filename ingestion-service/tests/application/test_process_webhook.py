import pytest
from unittest.mock import AsyncMock
from src.application.use_cases.process_webhook import ProcessWebhookUseCase
from src.domain.ports.repository import CodeChangeRepository
from src.domain.exceptions import MappingError


# --- Helpers ---

def a_push_payload(**overrides):
    payload = {
        "ref": "refs/heads/main",
        "after": "sha123abc",
        "repository": {"full_name": "user/project"},
    }
    payload.update(overrides)
    return payload


def a_pr_payload(**overrides):
    payload = {
        "number": 1,
        "pull_request": {"head": {"sha": "sha123abc"}},
        "repository": {"full_name": "user/project"},
    }
    payload.update(overrides)
    return payload


def a_use_case():
    mock_repo = AsyncMock(spec=CodeChangeRepository)
    return ProcessWebhookUseCase(repository=mock_repo), mock_repo


# --- push event ---

@pytest.mark.asyncio
async def test_push_calls_save_once():
    use_case, mock_repo = a_use_case()
    await use_case.execute(a_push_payload(), event_type="push")
    mock_repo.save.assert_called_once()


@pytest.mark.asyncio
async def test_push_maps_repository():
    use_case, mock_repo = a_use_case()
    await use_case.execute(a_push_payload(), event_type="push")
    assert mock_repo.save.call_args[0][0].repository == "user/project"


@pytest.mark.asyncio
async def test_push_maps_ref():
    use_case, mock_repo = a_use_case()
    await use_case.execute(a_push_payload(ref="refs/heads/feature"), event_type="push")
    assert mock_repo.save.call_args[0][0].ref == "refs/heads/feature"


@pytest.mark.asyncio
async def test_push_maps_target_sha():
    use_case, mock_repo = a_use_case()
    await use_case.execute(a_push_payload(after="deadbeef"), event_type="push")
    assert mock_repo.save.call_args[0][0].target_sha == "deadbeef"


@pytest.mark.asyncio
async def test_push_sets_event_type():
    use_case, mock_repo = a_use_case()
    await use_case.execute(a_push_payload(), event_type="push")
    assert mock_repo.save.call_args[0][0].event_type == "push"


@pytest.mark.asyncio
async def test_push_raises_on_malformed_payload():
    use_case, mock_repo = a_use_case()
    with pytest.raises(MappingError):
        await use_case.execute({"ref": "only-ref"}, event_type="push")


# --- pull_request event ---

@pytest.mark.asyncio
async def test_pr_calls_save_once():
    use_case, mock_repo = a_use_case()
    await use_case.execute(a_pr_payload(), event_type="pull_request")
    mock_repo.save.assert_called_once()


@pytest.mark.asyncio
async def test_pr_maps_repository():
    use_case, mock_repo = a_use_case()
    await use_case.execute(a_pr_payload(), event_type="pull_request")
    assert mock_repo.save.call_args[0][0].repository == "user/project"


@pytest.mark.asyncio
async def test_pr_formats_ref_with_pr_number():
    use_case, mock_repo = a_use_case()
    payload = a_pr_payload(number=99)
    await use_case.execute(payload, event_type="pull_request")
    assert mock_repo.save.call_args[0][0].ref == "pr/99"


@pytest.mark.asyncio
async def test_pr_maps_target_sha():
    use_case, mock_repo = a_use_case()
    payload = a_pr_payload()
    payload["pull_request"]["head"]["sha"] = "headsha99"
    await use_case.execute(payload, event_type="pull_request")
    assert mock_repo.save.call_args[0][0].target_sha == "headsha99"


@pytest.mark.asyncio
async def test_pr_sets_event_type():
    use_case, mock_repo = a_use_case()
    await use_case.execute(a_pr_payload(), event_type="pull_request")
    assert mock_repo.save.call_args[0][0].event_type == "pull_request"


@pytest.mark.asyncio
async def test_pr_raises_on_malformed_payload():
    use_case, mock_repo = a_use_case()
    with pytest.raises(MappingError):
        await use_case.execute({"number": 1}, event_type="pull_request")


# --- unsupported event ---

@pytest.mark.asyncio
async def test_unsupported_event_raises_mapping_error():
    use_case, mock_repo = a_use_case()
    with pytest.raises(MappingError):
        await use_case.execute({}, event_type="star")


@pytest.mark.asyncio
async def test_unsupported_event_names_the_bad_type():
    use_case, mock_repo = a_use_case()
    with pytest.raises(MappingError, match="star"):
        await use_case.execute({}, event_type="star")


@pytest.mark.asyncio
async def test_unsupported_event_does_not_call_save():
    use_case, mock_repo = a_use_case()
    with pytest.raises(MappingError):
        await use_case.execute({}, event_type="star")
    mock_repo.save.assert_not_called()
