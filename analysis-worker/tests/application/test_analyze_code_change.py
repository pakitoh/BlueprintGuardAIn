import pytest
from unittest.mock import AsyncMock
from src.application.use_cases.analyze_code_change import AnalyzeCodeChangeUseCase
from src.domain.entities import CodeChange, AnalysisResult


@pytest.mark.asyncio
async def test_analyze_code_change_use_case_success():
    # Arrange
    mock_repo = AsyncMock()
    use_case = AnalyzeCodeChangeUseCase(repository=mock_repo)

    code_change = CodeChange(
        repository="paco/blueprint",
        ref="main",
        target_sha="sha123",
        event_type="push",
        raw_payload={},
    )

    # Act
    await use_case.execute(code_change)

    # Assert
    mock_repo.save.assert_called_once()
    result = mock_repo.save.call_args[0][0]
    assert isinstance(result, AnalysisResult)
    assert result.repository == "paco/blueprint"
    assert result.sha == "sha123"
    assert result.status == "COMPLETED"
    assert "PASSED" in result.findings
