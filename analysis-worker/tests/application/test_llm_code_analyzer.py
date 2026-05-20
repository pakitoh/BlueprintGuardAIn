import pytest
from unittest.mock import AsyncMock

from src.domain.entities import CodeChange, PastFinding
from src.domain.ports.diff_fetcher import FileDiff
from src.application.services.finding_parser import FindingParser
from src.application.services.findings_validator import FindingsValidator
from src.application.services.llm_code_analyzer import LLMCodeAnalyzer
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
            "commits": [{"message": "Refactor auth module", "added": [], "modified": [], "removed": []}]
        }
    )


def a_file_diff(filename="src/domain/auth.py", status="modified", patch="+ def handle(): pass"):
    return FileDiff(filename=filename, status=status, patch=patch)


def an_analyzer(llm_client=None, diff_fetcher=None, findings_store=None):
    if llm_client is None:
        llm_client = AsyncMock()
        llm_client.call = AsyncMock(return_value="- Default finding")
    if diff_fetcher is None:
        diff_fetcher = AsyncMock()
        diff_fetcher.fetch = AsyncMock(return_value=[])
    if findings_store is None:
        findings_store = AsyncMock()
        findings_store.find_similar = AsyncMock(return_value=[])
        findings_store.save = AsyncMock()
    return LLMCodeAnalyzer(
        diff_fetcher=diff_fetcher,
        prompt_composer=PromptComposer(),
        llm_client=llm_client,
        findings_store=findings_store,
        finding_parser=FindingParser(),
        findings_validator=FindingsValidator(),
    )


# --- analyze ---


@pytest.mark.asyncio
async def test_analyze_returns_parsed_findings():
    llm_client = AsyncMock()
    llm_client.call = AsyncMock(return_value="- Concern A\n- Concern B")
    findings, status = await an_analyzer(llm_client=llm_client).analyze(a_change_with_commits())
    assert findings == ["Concern A", "Concern B"]
    assert status == "COMPLETED"


@pytest.mark.asyncio
async def test_analyze_returns_failed_status_on_llm_error():
    llm_client = AsyncMock()
    llm_client.call = AsyncMock(side_effect=Exception("LLM unavailable"))
    findings, status = await an_analyzer(llm_client=llm_client).analyze(a_change())
    assert findings == []
    assert status == "FAILED"


@pytest.mark.asyncio
async def test_analyze_returns_failed_status_when_llm_returns_empty_response():
    llm_client = AsyncMock()
    llm_client.call = AsyncMock(return_value="")
    findings, status = await an_analyzer(llm_client=llm_client).analyze(a_change())
    assert findings == []
    assert status == "FAILED"


@pytest.mark.asyncio
async def test_analyze_returns_failed_status_when_llm_returns_none():
    llm_client = AsyncMock()
    llm_client.call = AsyncMock(return_value=None)
    findings, status = await an_analyzer(llm_client=llm_client).analyze(a_change())
    assert findings == []
    assert status == "FAILED"


@pytest.mark.asyncio
async def test_analyze_saves_to_store():
    llm_client = AsyncMock()
    llm_client.call = AsyncMock(return_value="- Finding X")
    findings_store = AsyncMock()
    findings_store.find_similar = AsyncMock(return_value=[])
    findings_store.save = AsyncMock()
    diff_fetcher = AsyncMock()
    diff_fetcher.fetch = AsyncMock(return_value=[])
    change = a_change_with_commits()
    await an_analyzer(
        llm_client=llm_client, diff_fetcher=diff_fetcher, findings_store=findings_store
    ).analyze(change)
    findings_store.save.assert_awaited_once_with(change, ["Finding X"], [])


@pytest.mark.asyncio
async def test_analyze_continues_when_diff_fetch_returns_empty():
    llm_client = AsyncMock()
    llm_client.call = AsyncMock(return_value="- Finding Z")
    diff_fetcher = AsyncMock()
    diff_fetcher.fetch = AsyncMock(return_value=[])
    findings, status = await an_analyzer(llm_client=llm_client, diff_fetcher=diff_fetcher).analyze(
        a_change()
    )
    assert findings == ["Finding Z"]
    assert status == "COMPLETED"


# --- _fetch_diffs ---


@pytest.mark.asyncio
async def test_fetch_diffs_returns_diffs_from_fetcher():
    fd = a_file_diff()
    diff_fetcher = AsyncMock()
    diff_fetcher.fetch = AsyncMock(return_value=[fd])
    result = await an_analyzer(diff_fetcher=diff_fetcher)._fetch_diffs(a_change())
    assert result == [fd]


# --- _fetch_past_findings ---


@pytest.mark.asyncio
async def test_fetch_past_findings_returns_findings_from_store():
    past = [PastFinding(rule_text="Avoid cross-layer imports", context="ctx")]
    findings_store = AsyncMock()
    findings_store.find_similar = AsyncMock(return_value=past)
    findings_store.save = AsyncMock()
    result = await an_analyzer(findings_store=findings_store)._fetch_past_findings(
        a_change(), []
    )
    assert result == past


@pytest.mark.asyncio
async def test_fetch_past_findings_returns_empty_when_store_returns_empty():
    findings_store = AsyncMock()
    findings_store.find_similar = AsyncMock(return_value=[])
    findings_store.save = AsyncMock()
    result = await an_analyzer(findings_store=findings_store)._fetch_past_findings(
        a_change(), []
    )
    assert result == []
