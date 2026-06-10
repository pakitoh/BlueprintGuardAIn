import structlog

from src.domain.entities import AnalysisResult, CodeChange
from src.domain.ports.analysis_result_repository import AnalysisResultRepository
from src.domain.ports.code_analyzer import CodeAnalyzer
from src.domain.ports.code_change_source import CodeChangeSource
from src.domain.ports.idempotency_store import IdempotencyStore

logger = structlog.get_logger()


class AnalyzeCodeChangeUseCase:
    def __init__(
        self,
        source: CodeChangeSource,
        sink: AnalysisResultRepository,
        analyzer: CodeAnalyzer,
        idempotency: IdempotencyStore,
    ):
        self._source = source
        self._sink = sink
        self._analyzer = analyzer
        self._idempotency = idempotency

    async def run(self) -> None:
        async for change in self._source.listen():
            await self._process_if_new(change)

    async def _process_if_new(self, change: CodeChange) -> None:
        key = f"{change.repository}@{change.target_sha}"
        if await self._idempotency.is_processed(key):
            logger.info(
                "duplicate_change_skipped",
                repo=change.repository,
                sha=change.target_sha,
            )
            return
        await self._process(change)
        await self._idempotency.mark_processed(key)

    async def _process(self, change: CodeChange) -> AnalysisResult:
        logger.info(
            "analyzing_code_change", repo=change.repository, sha=change.target_sha
        )
        findings, status = await self._analyzer.analyze(change)
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
