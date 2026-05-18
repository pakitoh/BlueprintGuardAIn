import asyncio
import structlog

from src.infrastructure.instrumentation import instrument_app
from src.infrastructure.factory import InfrastructureFactory
from src.infrastructure.tracing.instrumented_analyze_code_change import (
    InstrumentedAnalyzeCodeChangeUseCase,
)

logger = structlog.get_logger()


async def run_worker():
    instrument_app()

    factory = InfrastructureFactory()
    await factory.start()

    try:
        use_case = InstrumentedAnalyzeCodeChangeUseCase(
            source=factory.code_change_source,
            sink=factory.analysis_result_repository,
            analyzer=factory.code_analyzer,
        )
        logger.info("analysis_worker_ready")
        await use_case.run()
    finally:
        logger.info("stopping_analysis_worker")
        await factory.stop()


if __name__ == "__main__":
    asyncio.run(run_worker())
