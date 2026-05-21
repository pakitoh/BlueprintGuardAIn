import structlog
from typing import List
from src.domain.entities import AnalysisResult
from src.domain.ports.analysis_result_source import AnalysisResultSource
from src.domain.ports.action_port import ActionPort

logger = structlog.get_logger()


class ProcessAnalysisResultUseCase:
    def __init__(self, source: AnalysisResultSource, actions: List[ActionPort]):
        self._source = source
        self._actions = actions

    async def run(self) -> None:
        async for result in self._source.listen():
            try:
                await self._process(result)
            except Exception as e:
                logger.error("processing_failed", error=str(e), repo=result.repository)

    async def _process(self, result: AnalysisResult) -> None:
        logger.info(
            "processing_analysis_result",
            repo=result.repository,
            sha=result.sha,
            status=result.status,
        )
        for action in self._actions:
            try:
                await action.execute(result)
            except Exception as e:
                logger.error("action_failed", error=str(e), repo=result.repository)
        logger.info("analysis_result_processed", repo=result.repository)
