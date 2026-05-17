import pytest
from unittest.mock import AsyncMock
from src.application.use_cases.analyze_code_change import AnalyzeCodeChangeUseCase
from src.domain.entities import CodeChange


# --- Helpers ---


def a_code_change(repository="paco/blueprint", target_sha="sha123"):
    return CodeChange(
        repository=repository,
        ref="main",
        target_sha=target_sha,
        event_type="push",
        raw_payload={},
    )


def a_process_use_case():
    mock_sink = AsyncMock()
    use_case = AnalyzeCodeChangeUseCase(source=AsyncMock(), sink=mock_sink)
    return use_case, mock_sink


def a_run_use_case(changes):
    async def mock_listen():
        for c in changes:
            yield c

    mock_source = AsyncMock()
    mock_source.listen = mock_listen
    mock_sink = AsyncMock()
    return AnalyzeCodeChangeUseCase(source=mock_source, sink=mock_sink), mock_sink


# --- _process ---


@pytest.mark.asyncio
async def test_process_calls_sink_exactly_once():
    use_case, mock_sink = a_process_use_case()
    await use_case._process(a_code_change())
    mock_sink.save.assert_called_once()


@pytest.mark.asyncio
async def test_process_result_maps_repository():
    use_case, mock_sink = a_process_use_case()
    await use_case._process(a_code_change(repository="org/service"))
    result = mock_sink.save.call_args[0][0]
    assert result.repository == "org/service"


@pytest.mark.asyncio
async def test_process_result_maps_sha():
    use_case, mock_sink = a_process_use_case()
    await use_case._process(a_code_change(target_sha="abc123"))
    result = mock_sink.save.call_args[0][0]
    assert result.sha == "abc123"


@pytest.mark.asyncio
async def test_process_result_status_is_completed():
    use_case, mock_sink = a_process_use_case()
    await use_case._process(a_code_change())
    result = mock_sink.save.call_args[0][0]
    assert result.status == "COMPLETED"


@pytest.mark.asyncio
async def test_process_findings_reference_repository():
    use_case, mock_sink = a_process_use_case()
    await use_case._process(a_code_change(repository="org/service"))
    result = mock_sink.save.call_args[0][0]
    assert any("org/service" in f for f in result.findings)


@pytest.mark.asyncio
async def test_process_findings_reference_sha():
    use_case, mock_sink = a_process_use_case()
    await use_case._process(a_code_change(target_sha="abc123"))
    result = mock_sink.save.call_args[0][0]
    assert any("abc123" in f for f in result.findings)


@pytest.mark.asyncio
async def test_process_findings_contain_passed():
    use_case, mock_sink = a_process_use_case()
    await use_case._process(a_code_change())
    result = mock_sink.save.call_args[0][0]
    assert any("PASSED" in f for f in result.findings)


# --- run ---


@pytest.mark.asyncio
async def test_run_does_not_call_sink_when_source_is_empty():
    use_case, mock_sink = a_run_use_case([])
    await use_case.run()
    mock_sink.save.assert_not_called()


@pytest.mark.asyncio
async def test_run_calls_sink_once_per_change():
    use_case, mock_sink = a_run_use_case(
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
    use_case, mock_sink = a_run_use_case(
        [
            a_code_change(repository="org/a", target_sha="sha1"),
            a_code_change(repository="org/b", target_sha="sha2"),
        ]
    )
    await use_case.run()
    results = [call[0][0] for call in mock_sink.save.call_args_list]
    assert results[0].repository == "org/a" and results[0].sha == "sha1"
    assert results[1].repository == "org/b" and results[1].sha == "sha2"


@pytest.mark.asyncio
async def test_run_continues_processing_after_one_failure():
    use_case, mock_sink = a_run_use_case(
        [
            a_code_change(target_sha="sha1"),
            a_code_change(target_sha="sha2"),
            a_code_change(target_sha="sha3"),
        ]
    )
    mock_sink.save.side_effect = [Exception("transient failure"), None, None]
    await use_case.run()
    assert mock_sink.save.call_count == 3


@pytest.mark.asyncio
async def test_run_does_not_raise_on_failure():
    use_case, mock_sink = a_run_use_case([a_code_change()])
    mock_sink.save.side_effect = Exception("sink down")
    await use_case.run()  # must not raise
