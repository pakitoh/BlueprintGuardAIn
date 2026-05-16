import pytest
from unittest.mock import AsyncMock
from src.application.use_cases.analyze_code_change import AnalyzeCodeChangeUseCase
from src.domain.entities import CodeChange, AnalysisResult


@pytest.mark.asyncio
async def test_process_saves_analysis_result():
    use_case = AnalyzeCodeChangeUseCase(source=AsyncMock(), sink=AsyncMock())
    code_change = CodeChange(
        repository="paco/blueprint",
        ref="main",
        target_sha="sha123",
        event_type="push",
        raw_payload={},
    )

    await use_case._process(code_change)

    use_case._sink.save.assert_called_once()
    result = use_case._sink.save.call_args[0][0]
    assert isinstance(result, AnalysisResult)
    assert result.repository == "paco/blueprint"
    assert result.sha == "sha123"
    assert result.status == "COMPLETED"
    assert any("PASSED" in f for f in result.findings)


@pytest.mark.asyncio
async def test_run_processes_all_changes():
    changes = [
        CodeChange(
            repository="repo",
            ref="main",
            target_sha="sha1",
            event_type="push",
            raw_payload={},
        ),
        CodeChange(
            repository="repo",
            ref="main",
            target_sha="sha2",
            event_type="push",
            raw_payload={},
        ),
    ]

    async def mock_listen():
        for c in changes:
            yield c

    mock_source = AsyncMock()
    mock_source.listen = mock_listen
    mock_sink = AsyncMock()

    use_case = AnalyzeCodeChangeUseCase(source=mock_source, sink=mock_sink)
    await use_case.run()

    assert mock_sink.save.call_count == 2
