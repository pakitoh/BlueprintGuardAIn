from unittest.mock import AsyncMock

import pytest

from src.application.use_cases.process_webhook import ProcessWebhookUseCase
from src.domain.exceptions import MappingError, UnsupportedEventError
from src.domain.ports.repository import CodeChangeRepository
from src.infrastructure.idempotency.in_memory_store import InMemoryIdempotencyStore

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
    store = InMemoryIdempotencyStore(ttl_seconds=3600)
    use_case = ProcessWebhookUseCase(repository=mock_repo, idempotency_store=store)
    return use_case, mock_repo


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
    use_case, _mock_repo = a_use_case()
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
    use_case, _mock_repo = a_use_case()
    with pytest.raises(MappingError):
        await use_case.execute({"number": 1}, event_type="pull_request")


# --- unsupported event ---


@pytest.mark.asyncio
async def test_unsupported_event_raises_unsupported_event_error():
    use_case, _mock_repo = a_use_case()
    with pytest.raises(UnsupportedEventError):
        await use_case.execute({}, event_type="star")


@pytest.mark.asyncio
async def test_unsupported_event_names_the_bad_type():
    use_case, _mock_repo = a_use_case()
    with pytest.raises(UnsupportedEventError, match="star"):
        await use_case.execute({}, event_type="star")


@pytest.mark.asyncio
async def test_unsupported_event_does_not_call_save():
    use_case, mock_repo = a_use_case()
    with pytest.raises(UnsupportedEventError):
        await use_case.execute({}, event_type="star")
    mock_repo.save.assert_not_called()


# --- idempotency (repo + target_sha dedup) ---


@pytest.mark.asyncio
async def test_same_repo_and_sha_is_processed_only_once():
    use_case, mock_repo = a_use_case()
    await use_case.execute(a_push_payload(after="dup-sha"), event_type="push")
    await use_case.execute(a_push_payload(after="dup-sha"), event_type="push")
    mock_repo.save.assert_called_once()


@pytest.mark.asyncio
async def test_distinct_shas_are_both_processed():
    use_case, mock_repo = a_use_case()
    await use_case.execute(a_push_payload(after="sha-1"), event_type="push")
    await use_case.execute(a_push_payload(after="sha-2"), event_type="push")
    assert mock_repo.save.call_count == 2


@pytest.mark.asyncio
async def test_dedup_is_source_agnostic_push_then_same_sha():
    # a dashboard-style re-trigger of the same commit is also deduped, with no
    # synthetic header involved — the key is the content (repo + sha)
    use_case, mock_repo = a_use_case()
    payload = a_push_payload(after="abc123")
    await use_case.execute(payload, event_type="push")
    await use_case.execute(payload, event_type="push")
    mock_repo.save.assert_called_once()


@pytest.mark.asyncio
async def test_failed_save_is_not_marked_so_retry_reprocesses():
    use_case, mock_repo = a_use_case()
    mock_repo.save.side_effect = [RuntimeError("kafka down"), None]
    with pytest.raises(RuntimeError):
        await use_case.execute(a_push_payload(after="retry-sha"), event_type="push")
    # the retry of the same commit must go through, not be skipped as duplicate
    await use_case.execute(a_push_payload(after="retry-sha"), event_type="push")
    assert mock_repo.save.call_count == 2
