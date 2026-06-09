import pytest

from src.domain.entities import AnalysisResult
from src.infrastructure.actions.log_action import LogAction


def a_result() -> AnalysisResult:
    return AnalysisResult(
        repository="owner/repo",
        sha="abc123",
        status="COMPLETED",
        findings=["finding-1"],
        timestamp="2026-01-01T00:00:00Z",
    )


@pytest.mark.asyncio
async def test_logs_analysis_result_without_raising(mocker):
    log = mocker.patch("src.infrastructure.actions.log_action.logger")
    action = LogAction()

    await action.execute(a_result())

    log.info.assert_called_once()
    kwargs = log.info.call_args.kwargs
    assert kwargs["repository"] == "owner/repo"
    assert kwargs["status"] == "COMPLETED"
