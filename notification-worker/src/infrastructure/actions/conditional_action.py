
from src.domain.entities import AnalysisResult
from src.domain.ports.action_port import ActionPort


class ConditionalAction(ActionPort):
    def __init__(self, inner: ActionPort, trigger_statuses: list[str]):
        self._inner = inner
        self._trigger_statuses = trigger_statuses

    async def execute(self, result: AnalysisResult) -> None:
        if result.status in self._trigger_statuses:
            await self._inner.execute(result)
