import asyncio
import structlog

from src.infrastructure.instrumentation import instrument_app
from src.infrastructure.factory import InfrastructureFactory

logger = structlog.get_logger()


async def run_worker():
    instrument_app()

    factory = InfrastructureFactory()
    source = factory.create_code_change_repository()
    sink = factory.create_analysis_result_repository()

    await source.start()
    await sink.start()

    use_case = factory.create_analyze_code_change_use_case(source, sink)
    logger.info("analysis_worker_ready")

    try:
        await use_case.run()
    finally:
        logger.info("stopping_analysis_worker")
        await source.stop()
        await sink.stop()


if __name__ == "__main__":
    asyncio.run(run_worker())
