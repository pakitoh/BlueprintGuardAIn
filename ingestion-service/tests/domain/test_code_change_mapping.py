import pytest

from src.domain.entities.code_change import CodeChange
from src.domain.exceptions import MappingError

# --- Helpers ---


def a_push_payload(**overrides):
    payload = {
        "ref": "refs/heads/main",
        "after": "d4e5f6g7h8",
        "repository": {"full_name": "paco/blueprint-guardain"},
    }
    payload.update(overrides)
    return payload


def a_pr_payload(**overrides):
    payload = {
        "number": 42,
        "pull_request": {"head": {"sha": "a1b2c3d4"}},
        "repository": {"full_name": "paco/blueprint-guardain"},
    }
    payload.update(overrides)
    return payload


# --- from_push_event ---


def test_push_maps_repository():
    change = CodeChange.from_push_event(a_push_payload())
    assert change.repository == "paco/blueprint-guardain"


def test_push_maps_ref():
    change = CodeChange.from_push_event(a_push_payload(ref="refs/heads/feature"))
    assert change.ref == "refs/heads/feature"


def test_push_maps_target_sha_from_after():
    change = CodeChange.from_push_event(a_push_payload(after="abc123"))
    assert change.target_sha == "abc123"


def test_push_sets_event_type():
    change = CodeChange.from_push_event(a_push_payload())
    assert change.event_type == "push"


def test_push_preserves_raw_payload():
    payload = a_push_payload()
    change = CodeChange.from_push_event(payload)
    assert change.raw_payload is payload


def test_push_raises_on_missing_keys():
    with pytest.raises(MappingError, match="Missing required field"):
        CodeChange.from_push_event({"ref": "only-ref-no-repo"})


# --- from_pull_request_event ---


def test_pr_maps_repository():
    change = CodeChange.from_pull_request_event(a_pr_payload())
    assert change.repository == "paco/blueprint-guardain"


def test_pr_formats_ref_with_pr_number():
    change = CodeChange.from_pull_request_event(a_pr_payload(number=7))
    assert change.ref == "pr/7"


def test_pr_maps_target_sha_from_head():
    payload = a_pr_payload()
    payload["pull_request"]["head"]["sha"] = "headsha99"
    change = CodeChange.from_pull_request_event(payload)
    assert change.target_sha == "headsha99"


def test_pr_sets_event_type():
    change = CodeChange.from_pull_request_event(a_pr_payload())
    assert change.event_type == "pull_request"


def test_pr_preserves_raw_payload():
    payload = a_pr_payload()
    change = CodeChange.from_pull_request_event(payload)
    assert change.raw_payload is payload


def test_pr_raises_on_missing_keys():
    with pytest.raises(MappingError, match="Missing required field"):
        CodeChange.from_pull_request_event({"number": 1})


# --- __post_init__ validation ---


def test_raises_when_repository_is_empty():
    with pytest.raises(MappingError, match="Repository cannot be empty"):
        CodeChange(
            repository="",
            ref="main",
            target_sha="sha",
            event_type="push",
            raw_payload={},
        )


def test_raises_when_target_sha_is_empty():
    with pytest.raises(MappingError, match="Target SHA cannot be empty"):
        CodeChange(
            repository="org/repo",
            ref="main",
            target_sha="",
            event_type="push",
            raw_payload={},
        )


def test_raises_when_event_type_is_empty():
    with pytest.raises(MappingError, match="Event type cannot be empty"):
        CodeChange(
            repository="org/repo",
            ref="main",
            target_sha="sha",
            event_type="",
            raw_payload={},
        )
