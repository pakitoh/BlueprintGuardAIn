from src.domain.entities import CodeChange, PastFinding
from src.domain.ports.diff_fetcher import FileDiff
from src.application.services.prompt_config import (
    NONE_LISTED_PLACEHOLDER,
    NO_PATCH_PLACEHOLDER,
)
from src.application.services.prompt_composer import PromptComposer


def a_change(repository="org/service", raw_payload=None):
    return CodeChange(
        repository=repository,
        ref="refs/heads/main",
        target_sha="abc123",
        event_type="push",
        raw_payload=raw_payload or {},
    )


def a_change_with_commits():
    return a_change(
        raw_payload={
            "commits": [
                {
                    "message": "Refactor auth module",
                    "added": ["src/auth/handler.py"],
                    "modified": ["src/auth/service.py"],
                    "removed": ["src/auth/legacy.py"],
                }
            ]
        }
    )


def a_file_diff(
    filename="src/domain/auth.py", status="modified", patch="+ def handle(): pass"
):
    return FileDiff(filename=filename, status=status, patch=patch)


def a_composer():
    return PromptComposer()


# --- build ---


def test_build_contains_repository():
    prompt = a_composer().build(a_change(repository="org/my-service"), [], [])
    assert "org/my-service" in prompt


def test_build_includes_file_patch():
    fd = a_file_diff(filename="src/auth/handler.py", patch="+ def handle(): pass")
    prompt = a_composer().build(a_change_with_commits(), [fd], [])
    assert "src/auth/handler.py" in prompt
    assert "+ def handle(): pass" in prompt


def test_build_contains_commit_message():
    prompt = a_composer().build(a_change_with_commits(), [], [])
    assert "Refactor auth module" in prompt


def test_build_handles_empty_payload():
    prompt = a_composer().build(a_change(raw_payload={}), [], [])
    assert "none listed" in prompt


def test_build_skips_lock_files():
    fd = a_file_diff(filename="poetry.lock", patch="+ some lock content")
    prompt = a_composer().build(a_change(), [fd], [])
    assert "poetry.lock" not in prompt


def test_build_includes_size_warning_when_files_dropped():
    big_patch = "+" + "x" * 3000
    fds = [
        a_file_diff(filename=f"src/domain/file{i}.py", patch=big_patch)
        for i in range(10)
    ]
    prompt = a_composer().build(a_change(), fds, [])
    assert "excluded" in prompt
    assert "too large" in prompt


def test_build_includes_similar_findings_when_present():
    past = [PastFinding(rule_text="Avoid cross-layer imports", context="ctx")]
    prompt = a_composer().build(a_change_with_commits(), [], past)
    assert "Avoid cross-layer imports" in prompt


# --- _format_patch_section ---


def test_format_patch_section_joins_included_chunks():
    result = a_composer()._format_patch_section(["chunk A\n", "chunk B\n"])
    assert "chunk A" in result
    assert "chunk B" in result


def test_format_patch_section_returns_placeholder_when_empty():
    result = a_composer()._format_patch_section([])
    assert result == NO_PATCH_PLACEHOLDER + "\n"


# --- _format_size_note ---


def test_format_size_note_returns_empty_when_nothing_dropped():
    assert a_composer()._format_size_note([]) == ""


def test_format_size_note_includes_count_and_filenames():
    result = a_composer()._format_size_note(["src/a.py", "src/b.py"])
    assert "2" in result
    assert "src/a.py" in result
    assert "src/b.py" in result


# --- _format_messages_section ---


def test_format_messages_section_formats_commit_messages():
    result = a_composer()._format_messages_section(a_change_with_commits())
    assert "Refactor auth module" in result


def test_format_messages_section_returns_placeholder_when_no_commits():
    result = a_composer()._format_messages_section(a_change(raw_payload={}))
    assert result == NONE_LISTED_PLACEHOLDER


# --- _format_examples_section ---


def test_format_examples_section_formats_past_findings():
    past = [PastFinding(rule_text="Avoid cross-layer imports", context="ctx")]
    result = a_composer()._format_examples_section(past)
    assert "Avoid cross-layer imports" in result


def test_format_examples_section_returns_empty_when_no_past():
    result = a_composer()._format_examples_section([])
    assert result == ""


# --- _select_files_for_review ---


def test_select_files_excludes_lock_files():
    fd = a_file_diff(filename="poetry.lock", patch="+ lock content")
    included, dropped = a_composer()._select_files_for_review([fd])
    assert included == []
    assert dropped == []


def test_select_files_prioritises_domain_over_tests():
    domain_fd = a_file_diff(filename="src/domain/entity.py", patch="+ class Foo: pass")
    test_fd = a_file_diff(
        filename="tests/test_entity.py", patch="+ def test_foo(): pass"
    )
    included, _ = a_composer()._select_files_for_review([test_fd, domain_fd])
    assert "domain/entity.py" in included[0]
    assert "test_entity.py" in included[1]


def test_select_files_drops_files_beyond_budget():
    big_patch = "+" + "x" * 3000
    fds = [
        a_file_diff(filename=f"src/domain/file{i}.py", patch=big_patch)
        for i in range(10)
    ]
    included, dropped = a_composer()._select_files_for_review(fds)
    assert len(included) + len(dropped) == 10
    assert len(dropped) > 0
