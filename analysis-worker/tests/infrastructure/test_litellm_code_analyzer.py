import pytest
from unittest.mock import AsyncMock, MagicMock
from src.domain.entities import CodeChange, PastFinding
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


def an_analyzer(findings_store=None):
    if findings_store is None:
        findings_store = AsyncMock()
        findings_store.find_similar = AsyncMock(return_value=[])
        findings_store.save = AsyncMock()
    return LiteLLMCodeAnalyzer(
        model="gemini/gemini-2.0-flash",
        api_key="test-key",
        findings_store=findings_store,
    )


# --- _build_prompt ---


@pytest.mark.asyncio
async def test_build_prompt_contains_repository():
    prompt = await an_analyzer()._build_prompt(a_change(repository="org/my-service"))
    assert "org/my-service" in prompt


@pytest.mark.asyncio
async def test_build_prompt_contains_added_files():
    prompt = await an_analyzer()._build_prompt(a_change_with_commits())
    assert "src/auth/handler.py" in prompt


@pytest.mark.asyncio
async def test_build_prompt_contains_modified_files():
    prompt = await an_analyzer()._build_prompt(a_change_with_commits())
    assert "src/auth/service.py" in prompt


@pytest.mark.asyncio
async def test_build_prompt_contains_commit_message():
    prompt = await an_analyzer()._build_prompt(a_change_with_commits())
    assert "Refactor auth module" in prompt


@pytest.mark.asyncio
async def test_build_prompt_handles_empty_payload():
    prompt = await an_analyzer()._build_prompt(a_change(raw_payload={}))
    assert "none listed" in prompt


@pytest.mark.asyncio
async def test_build_prompt_includes_similar_findings_when_present():
    store = AsyncMock()
    store.find_similar = AsyncMock(
        return_value=[PastFinding(rule_text="Avoid cross-layer imports", context="ctx")]
    )
    store.save = AsyncMock()
    prompt = await an_analyzer(findings_store=store)._build_prompt(a_change_with_commits())
    assert "Avoid cross-layer imports" in prompt


@pytest.mark.asyncio
async def test_build_prompt_still_works_when_store_raises():
    store = AsyncMock()
    store.find_similar = AsyncMock(side_effect=Exception("DB down"))
    store.save = AsyncMock()
    prompt = await an_analyzer(findings_store=store)._build_prompt(a_change())
    assert "architectural observations" in prompt


# --- _call_llm ---


@pytest.mark.asyncio
async def test_call_llm_passes_correct_model_and_prompt(mock_litellm):
    await an_analyzer()._call_llm("my prompt")
    mock_litellm.assert_awaited_once_with(
        model="gemini/gemini-2.0-flash",
        messages=[{"role": "user", "content": "my prompt"}],
        api_key="test-key",
    )


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


# --- analyze (orchestration) ---


@pytest.mark.asyncio
async def test_analyze_returns_parsed_findings(mock_litellm):
    mock_litellm.return_value.choices[0].message.content = "- Concern A\n- Concern B"
    findings = await an_analyzer().analyze(a_change_with_commits())
    assert findings == ["Concern A", "Concern B"]


@pytest.mark.asyncio
async def test_analyze_saves_to_store(mock_litellm):
    mock_litellm.return_value.choices[0].message.content = "- Finding X"
    store = AsyncMock()
    store.find_similar = AsyncMock(return_value=[])
    store.save = AsyncMock()
    change = a_change_with_commits()
    await an_analyzer(findings_store=store).analyze(change)
    store.save.assert_awaited_once_with(change, ["Finding X"])


@pytest.mark.asyncio
async def test_analyze_still_returns_findings_when_save_fails(mock_litellm):
    mock_litellm.return_value.choices[0].message.content = "- Finding Y"
    store = AsyncMock()
    store.find_similar = AsyncMock(return_value=[])
    store.save = AsyncMock(side_effect=Exception("write error"))
    findings = await an_analyzer(findings_store=store).analyze(a_change())
    assert findings == ["Finding Y"]
