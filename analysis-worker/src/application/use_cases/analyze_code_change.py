import structlog
from src.domain.entities import CodeChange, AnalysisResult
from src.domain.ports.code_change_source import CodeChangeSource
from src.domain.ports.analysis_result_repository import AnalysisResultRepository
from src.domain.ports.code_analyzer import CodeAnalyzer

logger = structlog.get_logger()


class AnalyzeCodeChangeUseCase:
    def __init__(
        self,
        source: CodeChangeSource,
        sink: AnalysisResultRepository,
        analyzer: CodeAnalyzer,
    ):
        self._source = source
        self._sink = sink
        self._analyzer = analyzer

    async def run(self) -> None:
        async for change in self._source.listen():
            try:
                await self._process(change)
            except Exception as e:
                logger.error("processing_failed", error=str(e), repo=change.repository)

    async def _process(self, change: CodeChange) -> AnalysisResult:
        logger.info(
            "analyzing_code_change", repo=change.repository, sha=change.target_sha
        )
        try:
            findings = await self._analyzer.analyze(change)
            status = "COMPLETED"
        except Exception as e:
            logger.error("llm_analysis_failed", error=str(e), repo=change.repository)
            findings = []
            status = "FAILED"
        result = AnalysisResult(
            repository=change.repository,
            sha=change.target_sha,
            status=status,
            findings=findings,
            ingested_at=change.timestamp,
        )
        await self._sink.save(result)
        logger.info("analysis_completed", repo=result.repository, status=result.status)
        return result
