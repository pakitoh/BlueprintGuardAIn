from src.application.use_cases.analyze_code_change import AnalyzeCodeChangeUseCase
from src.domain.entities import CodeChange
from src.infrastructure.tracing.decorators import traced


class InstrumentedAnalyzeCodeChangeUseCase(AnalyzeCodeChangeUseCase):
    @traced("process_code_change")
    async def _process(self, change: CodeChange) -> None:
        await super()._process(change)
