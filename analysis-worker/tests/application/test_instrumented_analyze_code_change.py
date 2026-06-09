from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.domain.entities import CodeChange
from src.infrastructure.tracing.instrumented_analyze_code_change import (
    InstrumentedAnalyzeCodeChangeUseCase,
)


def a_change() -> CodeChange:
    return CodeChange(
        repository="org/repo",
        ref="main",
        target_sha="sha123",
        event_type="push",
        raw_payload={},
        timestamp=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_process_returns_result_and_saves_via_sink():
    analyzer = AsyncMock()
    analyzer.analyze = AsyncMock(return_value=(["finding-1"], "COMPLETED"))
    sink = AsyncMock()
    use_case = InstrumentedAnalyzeCodeChangeUseCase(
        source=AsyncMock(), sink=sink, analyzer=analyzer
    )

    result = await use_case._process(a_change())

    assert result.status == "COMPLETED"
    assert result.findings == ["finding-1"]
    sink.save.assert_awaited_once_with(result)
