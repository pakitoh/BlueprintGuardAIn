import pytest
from unittest.mock import AsyncMock, MagicMock
from litellm import ServiceUnavailableError
from src.domain.entities import CodeChange, PastFinding
from src.domain.ports.diff_fetcher import FileDiff
from src.infrastructure.llm.analyzer_config import (
    NONE_LISTED_PLACEHOLDER,
    NO_PATCH_PLACEHOLDER,
    LLM_TIMEOUT,
)
from src.infrastructure.llm.litellm_code_analyzer import LiteLLMCodeAnalyzer


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


def an_analyzer(findings_store=None, diff_fetcher=None):
    if findings_store is None:
        findings_store = AsyncMock()
        findings_store.find_similar = AsyncMock(return_value=[])
        findings_store.save = AsyncMock()
    if diff_fetcher is None:
        diff_fetcher = AsyncMock()
        diff_fetcher.fetch = AsyncMock(return_value=[])
    return LiteLLMCodeAnalyzer(
        model="gemini/gemini-2.0-flash",
        api_key="test-key",
        findings_store=findings_store,
        diff_fetcher=diff_fetcher,
    )


# --- _build_prompt ---


@pytest.mark.asyncio
async def test_build_prompt_contains_repository():
    prompt = await an_analyzer()._build_prompt(
        a_change(repository="org/my-service"), []
    )
    assert "org/my-service" in prompt


@pytest.mark.asyncio
async def test_build_prompt_includes_file_patch():
    fd = a_file_diff(filename="src/auth/handler.py", patch="+ def handle(): pass")
    prompt = await an_analyzer()._build_prompt(a_change_with_commits(), [fd])
    assert "src/auth/handler.py" in prompt
    assert "+ def handle(): pass" in prompt


@pytest.mark.asyncio
async def test_build_prompt_contains_commit_message():
    prompt = await an_analyzer()._build_prompt(a_change_with_commits(), [])
    assert "Refactor auth module" in prompt


@pytest.mark.asyncio
async def test_build_prompt_handles_empty_payload():
    prompt = await an_analyzer()._build_prompt(a_change(raw_payload={}), [])
    assert "none listed" in prompt


@pytest.mark.asyncio
async def test_build_prompt_skips_lock_files():
    fd = a_file_diff(filename="poetry.lock", patch="+ some lock content")
    prompt = await an_analyzer()._build_prompt(a_change(), [fd])
    assert "poetry.lock" not in prompt


@pytest.mark.asyncio
async def test_build_prompt_includes_size_warning_when_files_dropped():
    big_patch = "+" + "x" * 3000
    fds = [
        a_file_diff(filename=f"src/domain/file{i}.py", patch=big_patch)
        for i in range(10)
    ]
    prompt = await an_analyzer()._build_prompt(a_change(), fds)
    assert "excluded" in prompt
    assert "too large" in prompt


@pytest.mark.asyncio
async def test_build_prompt_includes_similar_findings_when_present():
    store = AsyncMock()
    store.find_similar = AsyncMock(
        return_value=[PastFinding(rule_text="Avoid cross-layer imports", context="ctx")]
    )
    store.save = AsyncMock()
    prompt = await an_analyzer(findings_store=store)._build_prompt(
        a_change_with_commits(), []
    )
    assert "Avoid cross-layer imports" in prompt


@pytest.mark.asyncio
async def test_build_prompt_still_works_when_store_raises():
    store = AsyncMock()
    store.find_similar = AsyncMock(side_effect=Exception("DB down"))
    store.save = AsyncMock()
    prompt = await an_analyzer(findings_store=store)._build_prompt(a_change(), [])
    assert "architectural observations" in prompt


# --- _call_llm ---


@pytest.mark.asyncio
async def test_call_llm_passes_correct_model_and_prompt(mock_litellm):
    await an_analyzer()._call_llm("my prompt")
    mock_litellm.assert_awaited_once_with(
        model="gemini/gemini-2.0-flash",
        messages=[{"role": "user", "content": "my prompt"}],
        api_key="test-key",
        timeout=LLM_TIMEOUT,
    )


@pytest.mark.asyncio
async def test_call_llm_retries_on_service_unavailable(mock_litellm):
    good_response = MagicMock()
    good_response.choices[0].message.content = "Finding after retry"
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_litellm.side_effect = [
        ServiceUnavailableError(
            message="overloaded",
            llm_provider="gemini",
            model="gemini-2.0-flash",
            response=mock_response,
        ),
        good_response,
    ]
    result = await an_analyzer()._call_llm("any prompt")
    assert result == "Finding after retry"
    assert mock_litellm.await_count == 2


@pytest.mark.asyncio
async def test_call_llm_returns_response_content(mock_litellm):
    mock_litellm.return_value.choices[0].message.content = "LLM finding"
    result = await an_analyzer()._call_llm("prompt")
    assert result == "LLM finding"


# --- _parse_response ---


def test_parse_response_splits_lines_into_findings():
    findings = an_analyzer()._parse_response("Finding one\nFinding two\nFinding three")
    assert findings == ["Finding one", "Finding two", "Finding three"]


def test_parse_response_strips_bullet_markers():
    findings = an_analyzer()._parse_response("- Finding A\n* Finding B\n• Finding C")
    assert findings == ["Finding A", "Finding B", "Finding C"]


def test_parse_response_strips_numbered_markers():
    findings = an_analyzer()._parse_response("1. Finding A\n2) Finding B")
    assert findings == ["Finding A", "Finding B"]


def test_parse_response_filters_empty_lines():
    findings = an_analyzer()._parse_response("Finding A\n\n\nFinding B")
    assert findings == ["Finding A", "Finding B"]


def test_parse_response_raises_on_none():
    with pytest.raises(ValueError, match="empty response"):
        an_analyzer()._parse_response(None)


def test_parse_response_raises_on_empty_string():
    with pytest.raises(ValueError, match="empty response"):
        an_analyzer()._parse_response("")


# --- analyze (orchestration) ---


@pytest.mark.asyncio
async def test_analyze_returns_parsed_findings(mock_litellm):
    mock_litellm.return_value.choices[0].message.content = "- Concern A\n- Concern B"
    findings, status = await an_analyzer().analyze(a_change_with_commits())
    assert findings == ["Concern A", "Concern B"]
    assert status == "COMPLETED"


@pytest.mark.asyncio
async def test_analyze_returns_failed_status_on_llm_error(mock_litellm):
    mock_litellm.side_effect = Exception("LLM unavailable")
    findings, status = await an_analyzer().analyze(a_change())
    assert findings == []
    assert status == "FAILED"


@pytest.mark.asyncio
async def test_analyze_returns_failed_status_when_llm_returns_empty_response(
    mock_litellm,
):
    mock_litellm.return_value.choices[0].message.content = ""
    findings, status = await an_analyzer().analyze(a_change())
    assert findings == []
    assert status == "FAILED"


@pytest.mark.asyncio
async def test_analyze_returns_failed_status_when_llm_returns_none(mock_litellm):
    mock_litellm.return_value.choices[0].message.content = None
    findings, status = await an_analyzer().analyze(a_change())
    assert findings == []
    assert status == "FAILED"


@pytest.mark.asyncio
async def test_analyze_saves_to_store(mock_litellm):
    mock_litellm.return_value.choices[0].message.content = "- Finding X"
    store = AsyncMock()
    store.find_similar = AsyncMock(return_value=[])
    store.save = AsyncMock()
    diff_fetcher = AsyncMock()
    diff_fetcher.fetch = AsyncMock(return_value=[])
    change = a_change_with_commits()
    await an_analyzer(findings_store=store, diff_fetcher=diff_fetcher).analyze(change)
    store.save.assert_awaited_once_with(change, ["Finding X"], [])


@pytest.mark.asyncio
async def test_analyze_continues_when_diff_fetch_fails(mock_litellm):
    mock_litellm.return_value.choices[0].message.content = "- Finding Z"
    diff_fetcher = AsyncMock()
    diff_fetcher.fetch = AsyncMock(side_effect=Exception("GitHub API down"))
    findings, status = await an_analyzer(diff_fetcher=diff_fetcher).analyze(a_change())
    assert findings == ["Finding Z"]
    assert status == "COMPLETED"


# --- _format_patch_section ---


def test_format_patch_section_joins_included_chunks():
    result = an_analyzer()._format_patch_section(["chunk A\n", "chunk B\n"])
    assert "chunk A" in result
    assert "chunk B" in result


def test_format_patch_section_returns_placeholder_when_empty():
    result = an_analyzer()._format_patch_section([])
    assert result == NO_PATCH_PLACEHOLDER + "\n"


# --- _format_size_note ---


def test_format_size_note_returns_empty_when_nothing_dropped():
    assert an_analyzer()._format_size_note([]) == ""


def test_format_size_note_includes_count_and_filenames():
    result = an_analyzer()._format_size_note(["src/a.py", "src/b.py"])
    assert "2" in result
    assert "src/a.py" in result
    assert "src/b.py" in result


# --- _format_messages_section ---


def test_format_messages_section_formats_commit_messages():
    result = an_analyzer()._format_messages_section(a_change_with_commits())
    assert "Refactor auth module" in result


def test_format_messages_section_returns_placeholder_when_no_commits():
    result = an_analyzer()._format_messages_section(a_change(raw_payload={}))
    assert result == NONE_LISTED_PLACEHOLDER


# --- _fetch_examples_section ---


@pytest.mark.asyncio
async def test_fetch_examples_section_formats_similar_findings():
    store = AsyncMock()
    store.find_similar = AsyncMock(
        return_value=[PastFinding(rule_text="Avoid cross-layer imports", context="ctx")]
    )
    result = await an_analyzer(findings_store=store)._fetch_examples_section(
        a_change(), []
    )
    assert "Avoid cross-layer imports" in result


@pytest.mark.asyncio
async def test_fetch_examples_section_returns_empty_when_no_similar():
    store = AsyncMock()
    store.find_similar = AsyncMock(return_value=[])
    result = await an_analyzer(findings_store=store)._fetch_examples_section(
        a_change(), []
    )
    assert result == ""


@pytest.mark.asyncio
async def test_fetch_examples_section_returns_empty_on_store_error():
    store = AsyncMock()
    store.find_similar = AsyncMock(side_effect=Exception("DB down"))
    result = await an_analyzer(findings_store=store)._fetch_examples_section(
        a_change(), []
    )
    assert result == ""


# --- _fetch_diffs ---


@pytest.mark.asyncio
async def test_fetch_diffs_returns_diffs_from_fetcher():
    fd = a_file_diff()
    diff_fetcher = AsyncMock()
    diff_fetcher.fetch = AsyncMock(return_value=[fd])
    result = await an_analyzer(diff_fetcher=diff_fetcher)._fetch_diffs(a_change())
    assert result == [fd]


@pytest.mark.asyncio
async def test_fetch_diffs_returns_empty_list_on_error():
    diff_fetcher = AsyncMock()
    diff_fetcher.fetch = AsyncMock(side_effect=Exception("network error"))
    result = await an_analyzer(diff_fetcher=diff_fetcher)._fetch_diffs(a_change())
    assert result == []


# --- _select_files_for_review ---


def test_select_files_excludes_lock_files():
    fd = a_file_diff(filename="poetry.lock", patch="+ lock content")
    included, dropped = an_analyzer()._select_files_for_review([fd])
    assert included == []
    assert dropped == []


def test_select_files_prioritises_domain_over_tests():
    domain_fd = a_file_diff(filename="src/domain/entity.py", patch="+ class Foo: pass")
    test_fd = a_file_diff(
        filename="tests/test_entity.py", patch="+ def test_foo(): pass"
    )
    included, _ = an_analyzer()._select_files_for_review([test_fd, domain_fd])
    assert "domain/entity.py" in included[0]
    assert "test_entity.py" in included[1]


def test_select_files_drops_files_beyond_budget():
    big_patch = "+" + "x" * 3000
    fds = [
        a_file_diff(filename=f"src/domain/file{i}.py", patch=big_patch)
        for i in range(10)
    ]
    included, dropped = an_analyzer()._select_files_for_review(fds)
    assert len(included) + len(dropped) == 10
    assert len(dropped) > 0
