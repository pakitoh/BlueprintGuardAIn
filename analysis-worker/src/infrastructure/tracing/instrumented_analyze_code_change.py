import time

from src.application.use_cases.analyze_code_change import AnalyzeCodeChangeUseCase
from src.domain.entities import AnalysisResult, CodeChange
from src.infrastructure.metrics import code_changes_analyzed, analysis_duration
from src.infrastructure.tracing.decorators import traced


class InstrumentedAnalyzeCodeChangeUseCase(AnalyzeCodeChangeUseCase):
    @traced("process_code_change")
    async def _process(self, change: CodeChange) -> AnalysisResult:
        start = time.perf_counter()
        result = await super()._process(change)
        duration = time.perf_counter() - start
        attrs = {"status": result.status}
        code_changes_analyzed.add(1, attrs)
        analysis_duration.record(duration, attrs)
        return result
