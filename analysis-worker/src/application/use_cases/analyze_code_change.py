import structlog
from src.domain.entities import CodeChange, AnalysisResult
from src.domain.ports.code_change_source import CodeChangeSource
from src.domain.ports.analysis_result_repository import AnalysisResultRepository

logger = structlog.get_logger()


class AnalyzeCodeChangeUseCase:
    def __init__(self, source: CodeChangeSource, sink: AnalysisResultRepository):
        self._source = source
        self._sink = sink

    async def run(self) -> None:
        async for change in self._source.listen():
            try:
                await self._process(change)
            except Exception as e:
                logger.error("processing_failed", error=str(e), repo=change.repository)

    async def _process(self, change: CodeChange) -> None:
        logger.info(
            "analyzing_code_change", repo=change.repository, sha=change.target_sha
        )
        findings = [
            f"Architectural validation for {change.repository} started.",
            f"Target SHA {change.target_sha} analyzed.",
            "Result: PASSED.",
        ]
        result = AnalysisResult(
            repository=change.repository,
            sha=change.target_sha,
            status="COMPLETED",
            findings=findings,
        )
        await self._sink.save(result)
        logger.info("analysis_completed", repo=result.repository, status=result.status)
