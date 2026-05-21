import asyncio
import structlog

from src.infrastructure.instrumentation import instrument_app, resolve_commit_sha
from src.infrastructure.factory import InfrastructureFactory
from src.infrastructure.tracing.instrumented_analyze_code_change import (
    InstrumentedAnalyzeCodeChangeUseCase,
)

logger = structlog.get_logger()


async def run_worker():
    instrument_app()
    version = resolve_commit_sha()

    factory = InfrastructureFactory()
    try:
        await factory.start()
        use_case = InstrumentedAnalyzeCodeChangeUseCase(
            source=factory.code_change_source,
            sink=factory.analysis_result_repository,
            analyzer=factory.code_analyzer,
        )
        logger.info("analysis_worker_ready", version=version)
        await use_case.run()
    except Exception:
        logger.exception("analysis_worker_failed")
        raise
    finally:
        logger.info("stopping_analysis_worker")
        await factory.stop()


if __name__ == "__main__":
    asyncio.run(run_worker())
