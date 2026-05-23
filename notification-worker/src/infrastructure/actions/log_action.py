import structlog

from src.domain.entities import AnalysisResult
from src.domain.ports.action_port import ActionPort

logger = structlog.get_logger()


class LogAction(ActionPort):
    async def execute(self, result: AnalysisResult) -> None:
        logger.info(
            "analysis_result_received",
            repository=result.repository,
            sha=result.sha,
            status=result.status,
            findings=result.findings,
        )
