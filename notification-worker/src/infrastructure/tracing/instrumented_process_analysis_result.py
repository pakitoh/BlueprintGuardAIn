import time
from datetime import datetime

from src.application.use_cases.process_analysis_result import (
    ProcessAnalysisResultUseCase,
)
from src.domain.entities import AnalysisResult
from src.infrastructure.metrics import (
    results_processed,
    action_duration,
    pipeline_duration,
)
from src.infrastructure.tracing.decorators import traced


class InstrumentedProcessAnalysisResultUseCase(ProcessAnalysisResultUseCase):
    @traced("process_analysis_result")
    async def _process(self, result: AnalysisResult) -> None:
        start = time.perf_counter()
        await super()._process(result)
        duration = time.perf_counter() - start

        attrs = {"status": result.status}
        results_processed.add(1, attrs)
        action_duration.record(duration, attrs)

        if result.ingested_at:
            try:
                ingested = datetime.fromisoformat(result.ingested_at)
                total = (datetime.now() - ingested).total_seconds()
                pipeline_duration.record(total, attrs)
            except ValueError:
                pass
