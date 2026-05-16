from src.application.use_cases.process_analysis_result import (
    ProcessAnalysisResultUseCase,
)
from src.domain.entities import AnalysisResult
from src.infrastructure.tracing.decorators import traced


class InstrumentedProcessAnalysisResultUseCase(ProcessAnalysisResultUseCase):
    @traced("process_analysis_result")
    async def _process(self, result: AnalysisResult) -> None:
        await super()._process(result)
