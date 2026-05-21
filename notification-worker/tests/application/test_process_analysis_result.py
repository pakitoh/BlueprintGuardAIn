import pytest
from unittest.mock import AsyncMock, MagicMock
from src.application.use_cases.process_analysis_result import (
    ProcessAnalysisResultUseCase,
)
from src.domain.entities import AnalysisResult
from src.domain.exceptions import ActionError


def a_result(
    repository="owner/repo",
    sha="abc123",
    status="FAILED",
    findings=None,
    timestamp="2026-01-01T00:00:00Z",
) -> AnalysisResult:
    return AnalysisResult(
        repository=repository,
        sha=sha,
        status=status,
        findings=findings if findings is not None else ["finding-1"],
        timestamp=timestamp,
    )


def a_source(results=None):
    source = MagicMock()

    async def _listen():
        for r in results or []:
            yield r

    source.listen = _listen
    return source


def a_use_case(results=None, actions=None):
    return ProcessAnalysisResultUseCase(
        source=a_source(results),
        actions=actions or [],
    )


class TestProcessAnalysisResultProcess:
    @pytest.mark.asyncio
    async def test_executes_all_actions(self):
        action_a = AsyncMock()
        action_b = AsyncMock()
        use_case = ProcessAnalysisResultUseCase(
            source=a_source([a_result()]),
            actions=[action_a, action_b],
        )

        await use_case.run()

        action_a.execute.assert_awaited_once()
        action_b.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_passes_result_to_action(self):
        action = AsyncMock()
        result = a_result(repository="org/svc", sha="def456", status="COMPLETED")
        use_case = ProcessAnalysisResultUseCase(
            source=a_source([result]),
            actions=[action],
        )

        await use_case.run()

        action.execute.assert_awaited_once_with(result)

    @pytest.mark.asyncio
    async def test_continues_after_action_failure(self):
        failing_action = AsyncMock()
        failing_action.execute.side_effect = ActionError("boom")
        succeeding_action = AsyncMock()
        use_case = ProcessAnalysisResultUseCase(
            source=a_source([a_result()]),
            actions=[failing_action, succeeding_action],
        )

        await use_case.run()

        succeeding_action.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_does_not_raise_on_action_failure(self):
        failing_action = AsyncMock()
        failing_action.execute.side_effect = ActionError("boom")
        use_case = ProcessAnalysisResultUseCase(
            source=a_source([a_result()]),
            actions=[failing_action],
        )

        await use_case.run()

    @pytest.mark.asyncio
    async def test_no_actions_does_not_raise(self):
        use_case = a_use_case(results=[a_result()], actions=[])

        await use_case.run()

    @pytest.mark.asyncio
    async def test_action_receives_correct_repository(self):
        action = AsyncMock()
        result = a_result(repository="org/my-service")
        use_case = ProcessAnalysisResultUseCase(
            source=a_source([result]),
            actions=[action],
        )

        await use_case.run()

        called_result = action.execute.call_args[0][0]
        assert called_result.repository == "org/my-service"

    @pytest.mark.asyncio
    async def test_action_receives_correct_sha(self):
        action = AsyncMock()
        result = a_result(sha="cafebabe")
        use_case = ProcessAnalysisResultUseCase(
            source=a_source([result]),
            actions=[action],
        )

        await use_case.run()

        called_result = action.execute.call_args[0][0]
        assert called_result.sha == "cafebabe"

    @pytest.mark.asyncio
    async def test_action_receives_correct_status(self):
        action = AsyncMock()
        result = a_result(status="COMPLETED")
        use_case = ProcessAnalysisResultUseCase(
            source=a_source([result]),
            actions=[action],
        )

        await use_case.run()

        called_result = action.execute.call_args[0][0]
        assert called_result.status == "COMPLETED"


class TestProcessAnalysisResultRun:
    @pytest.mark.asyncio
    async def test_empty_source_does_not_call_actions(self):
        action = AsyncMock()
        use_case = a_use_case(results=[], actions=[action])

        await use_case.run()

        action.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_processes_multiple_results(self):
        action = AsyncMock()
        results = [a_result(sha=f"sha{i}") for i in range(3)]
        use_case = ProcessAnalysisResultUseCase(
            source=a_source(results),
            actions=[action],
        )

        await use_case.run()

        assert action.execute.await_count == 3

    @pytest.mark.asyncio
    async def test_each_result_dispatched_to_action(self):
        action = AsyncMock()
        r1 = a_result(sha="sha1")
        r2 = a_result(sha="sha2")
        use_case = ProcessAnalysisResultUseCase(
            source=a_source([r1, r2]),
            actions=[action],
        )

        await use_case.run()

        calls = [c[0][0] for c in action.execute.call_args_list]
        assert r1 in calls
        assert r2 in calls

    @pytest.mark.asyncio
    async def test_continues_processing_after_action_error_on_first_result(self):
        action = AsyncMock()
        action.execute.side_effect = [ActionError("first failed"), None]
        results = [a_result(sha="sha1"), a_result(sha="sha2")]
        use_case = ProcessAnalysisResultUseCase(
            source=a_source(results),
            actions=[action],
        )

        await use_case.run()

        assert action.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_run_does_not_raise(self):
        action = AsyncMock()
        action.execute.side_effect = RuntimeError("unexpected")
        use_case = a_use_case(results=[a_result()], actions=[action])

        await use_case.run()
