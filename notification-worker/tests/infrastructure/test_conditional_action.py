from unittest.mock import AsyncMock

import pytest

from src.domain.entities import AnalysisResult
from src.infrastructure.actions.conditional_action import ConditionalAction


def a_result(status="FAILED") -> AnalysisResult:
    return AnalysisResult(
        repository="owner/repo",
        sha="abc123",
        status=status,
        findings=["finding-1"],
        timestamp="2026-01-01T00:00:00Z",
    )


def a_conditional_action(trigger_statuses=None):
    inner = AsyncMock()
    action = ConditionalAction(
        inner=inner,
        trigger_statuses=trigger_statuses
        if trigger_statuses is not None
        else ["FAILED"],
    )
    return action, inner


class TestConditionalAction:
    @pytest.mark.asyncio
    async def test_executes_inner_when_status_matches(self):
        action, inner = a_conditional_action(trigger_statuses=["FAILED"])

        await action.execute(a_result(status="FAILED"))

        inner.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_inner_when_status_does_not_match(self):
        action, inner = a_conditional_action(trigger_statuses=["FAILED"])

        await action.execute(a_result(status="PASSED"))

        inner.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_passes_result_to_inner(self):
        action, inner = a_conditional_action(trigger_statuses=["FAILED"])
        result = a_result(status="FAILED")

        await action.execute(result)

        inner.execute.assert_awaited_once_with(result)

    @pytest.mark.asyncio
    async def test_executes_for_any_matching_status_in_list(self):
        action, inner = a_conditional_action(trigger_statuses=["FAILED", "COMPLETED"])

        await action.execute(a_result(status="COMPLETED"))

        inner.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_for_status_not_in_multi_status_list(self):
        action, inner = a_conditional_action(trigger_statuses=["FAILED", "COMPLETED"])

        await action.execute(a_result(status="PASSED"))

        inner.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_trigger_statuses_never_fires(self):
        action, inner = a_conditional_action(trigger_statuses=[])

        await action.execute(a_result(status="FAILED"))

        inner.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_does_not_raise_when_skipped(self):
        action, _ = a_conditional_action(trigger_statuses=["FAILED"])

        await action.execute(a_result(status="PASSED"))
