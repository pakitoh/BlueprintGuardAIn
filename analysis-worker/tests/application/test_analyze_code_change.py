from unittest.mock import AsyncMock

import pytest

from src.application.use_cases.analyze_code_change import AnalyzeCodeChangeUseCase
from src.domain.entities import CodeChange


def a_code_change(repository="paco/blueprint", target_sha="sha123"):
    return CodeChange(
        repository=repository,
        ref="main",
        target_sha=target_sha,
        event_type="push",
        raw_payload={},
    )


def a_process_use_case(findings=None, status="COMPLETED"):
    mock_sink = AsyncMock()
    mock_analyzer = AsyncMock()
    mock_analyzer.analyze.return_value = (
        findings if findings is not None else ["finding-1"],
        status,
    )
    use_case = AnalyzeCodeChangeUseCase(
        source=AsyncMock(), sink=mock_sink, analyzer=mock_analyzer
    )
    return use_case, mock_sink, mock_analyzer


def a_run_use_case(changes, findings=None):
    async def mock_listen():
        for c in changes:
            yield c

    mock_source = AsyncMock()
    mock_source.listen = mock_listen
    mock_sink = AsyncMock()
    mock_analyzer = AsyncMock()
    mock_analyzer.analyze.return_value = (
        findings if findings is not None else ["finding-1"],
        "COMPLETED",
    )
    return (
        AnalyzeCodeChangeUseCase(
            source=mock_source, sink=mock_sink, analyzer=mock_analyzer
        ),
        mock_sink,
        mock_analyzer,
    )


# --- _process ---


@pytest.mark.asyncio
async def test_process_calls_analyzer_with_change():
    use_case, _, mock_analyzer = a_process_use_case()
    change = a_code_change()
    await use_case._process(change)
    mock_analyzer.analyze.assert_awaited_once_with(change)


@pytest.mark.asyncio
async def test_process_calls_sink_exactly_once():
    use_case, mock_sink, _ = a_process_use_case()
    await use_case._process(a_code_change())
    mock_sink.save.assert_called_once()


@pytest.mark.asyncio
async def test_process_result_maps_repository():
    use_case, mock_sink, _ = a_process_use_case()
    await use_case._process(a_code_change(repository="org/service"))
    result = mock_sink.save.call_args[0][0]
    assert result.repository == "org/service"


@pytest.mark.asyncio
async def test_process_result_maps_sha():
    use_case, mock_sink, _ = a_process_use_case()
    await use_case._process(a_code_change(target_sha="abc123"))
    result = mock_sink.save.call_args[0][0]
    assert result.sha == "abc123"


@pytest.mark.asyncio
async def test_process_result_includes_findings_from_analyzer():
    use_case, mock_sink, _ = a_process_use_case(findings=["issue A", "issue B"])
    await use_case._process(a_code_change())
    result = mock_sink.save.call_args[0][0]
    assert result.findings == ["issue A", "issue B"]


@pytest.mark.asyncio
async def test_process_result_status_is_completed_on_success():
    use_case, mock_sink, _ = a_process_use_case()
    await use_case._process(a_code_change())
    result = mock_sink.save.call_args[0][0]
    assert result.status == "COMPLETED"


@pytest.mark.asyncio
async def test_process_result_ingested_at_matches_change_timestamp():
    use_case, mock_sink, _ = a_process_use_case()
    change = a_code_change()
    await use_case._process(change)
    result = mock_sink.save.call_args[0][0]
    assert result.ingested_at == change.timestamp


@pytest.mark.asyncio
async def test_process_returns_analysis_result():
    use_case, _, _ = a_process_use_case()
    result = await use_case._process(a_code_change())
    assert result is not None
    assert result.status == "COMPLETED"


@pytest.mark.asyncio
async def test_process_result_status_is_failed_when_analyzer_returns_failed():
    use_case, mock_sink, _ = a_process_use_case(findings=[], status="FAILED")
    await use_case._process(a_code_change())
    result = mock_sink.save.call_args[0][0]
    assert result.status == "FAILED"


@pytest.mark.asyncio
async def test_process_result_findings_empty_when_analyzer_returns_failed():
    use_case, mock_sink, _ = a_process_use_case(findings=[], status="FAILED")
    await use_case._process(a_code_change())
    result = mock_sink.save.call_args[0][0]
    assert result.findings == []


@pytest.mark.asyncio
async def test_process_still_saves_result_when_analyzer_returns_failed():
    use_case, mock_sink, _ = a_process_use_case(findings=[], status="FAILED")
    await use_case._process(a_code_change())
    mock_sink.save.assert_called_once()


# --- run ---


@pytest.mark.asyncio
async def test_run_does_not_call_sink_when_source_is_empty():
    use_case, mock_sink, _ = a_run_use_case([])
    await use_case.run()
    mock_sink.save.assert_not_called()


@pytest.mark.asyncio
async def test_run_calls_sink_once_per_change():
    use_case, mock_sink, _ = a_run_use_case(
        [
            a_code_change(target_sha="sha1"),
            a_code_change(target_sha="sha2"),
            a_code_change(target_sha="sha3"),
        ]
    )
    await use_case.run()
    assert mock_sink.save.call_count == 3


@pytest.mark.asyncio
async def test_run_maps_each_change_to_correct_result():
    use_case, mock_sink, _ = a_run_use_case(
        [
            a_code_change(repository="org/a", target_sha="sha1"),
            a_code_change(repository="org/b", target_sha="sha2"),
        ]
    )
    await use_case.run()
    results = [call[0][0] for call in mock_sink.save.call_args_list]
    assert results[0].repository == "org/a" and results[0].sha == "sha1"
    assert results[1].repository == "org/b" and results[1].sha == "sha2"
