import asyncio
from src.config import settings
from src.infrastructure.factory import InfrastructureFactory
from src.infrastructure.instrumentation import instrument_app
from src.infrastructure.actions.conditional_action import ConditionalAction
from src.infrastructure.actions.github_action import GitHubAction
from src.infrastructure.actions.log_action import LogAction
from src.infrastructure.actions.slack_action import SlackAction
from src.infrastructure.tracing.instrumented_process_analysis_result import (
    InstrumentedProcessAnalysisResultUseCase,
)


async def run_worker():
    instrument_app()
    factory = InfrastructureFactory()
    await factory.start()
    try:
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
    finally:
        await factory.stop()


def main():
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
