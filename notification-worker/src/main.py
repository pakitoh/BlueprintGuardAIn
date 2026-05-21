import asyncio
import structlog

from src.config import settings
from src.infrastructure.factory import InfrastructureFactory
from src.infrastructure.instrumentation import instrument_app, resolve_commit_sha
from src.infrastructure.actions.conditional_action import ConditionalAction
from src.infrastructure.actions.github_action import GitHubAction
from src.infrastructure.actions.log_action import LogAction
from src.infrastructure.actions.slack_action import SlackAction
from src.infrastructure.tracing.instrumented_process_analysis_result import (
    InstrumentedProcessAnalysisResultUseCase,
)


logger = structlog.get_logger()


async def run_worker():
    instrument_app()
    version = resolve_commit_sha()
    factory = InfrastructureFactory()
    try:
        await factory.start()
        logger.info("notification_worker_ready", version=version)
        actions = [LogAction()]

        if settings.github_token:
            actions.append(
                ConditionalAction(
                    inner=GitHubAction(
                        token=settings.github_token,
                        api_url=settings.github_api_url,
                    ),
                    trigger_statuses=settings.github_trigger_statuses,
                )
            )

        if settings.slack_webhook_url:
            actions.append(
                ConditionalAction(
                    inner=SlackAction(webhook_url=settings.slack_webhook_url),
                    trigger_statuses=settings.slack_trigger_statuses,
                )
            )

        use_case = InstrumentedProcessAnalysisResultUseCase(
            source=factory.analysis_result_source,
            actions=actions,
        )
        await use_case.run()
    except Exception:
        logger.exception("notification_worker_failed")
        raise
    finally:
        await factory.stop()


def main():
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
