import httpx
import structlog

from src.domain.entities import AnalysisResult
from src.domain.exceptions import ActionError
from src.domain.ports.action_port import ActionPort

logger = structlog.get_logger()


class SlackAction(ActionPort):
    def __init__(self, webhook_url: str):
        self._webhook_url = webhook_url

    async def execute(self, result: AnalysisResult) -> None:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self._webhook_url,
                    json={"text": self._format_message(result)},
                )
                response.raise_for_status()
            logger.info("slack_notification_sent", repo=result.repository)
        except Exception as e:
            raise ActionError(f"Failed to send Slack notification: {e}") from e

    def _format_message(self, result: AnalysisResult) -> str:
        findings_text = "\n".join(f"• {f}" for f in result.findings)
        return (
            f"*[{result.status}]* `{result.repository}` @ `{result.sha}`"
            f"\n{findings_text}"
        )
