from collections.abc import Awaitable, Callable

from schema_registry.client import SchemaRegistryClient

from src.config import settings
from src.domain.entities import AnalysisRecord
from src.domain.ports.analysis_repository import AnalysisRepository
from src.domain.ports.replay_progress_repository import ReplayProgressRepository
from src.infrastructure.kafka.result_consumer import KafkaResultConsumer
from src.infrastructure.postgres.replay_progress_repository import (
    PostgresReplayProgressRepository,
)
from src.infrastructure.postgres.repository import PostgresAnalysisRepository


class InfrastructureFactory:
    def __init__(self) -> None:
        self._consumer: KafkaResultConsumer | None = None
        self._repo: PostgresAnalysisRepository | None = None
        self._replay_progress_repo: PostgresReplayProgressRepository | None = None

    async def start(
        self,
        on_result: Callable[[AnalysisRecord], Awaitable[None]] | None = None,
    ) -> None:
        self._repo = PostgresAnalysisRepository(dsn=settings.postgres_url)
        await self._repo.start()

        self._replay_progress_repo = PostgresReplayProgressRepository(
            dsn=settings.postgres_url
        )
        await self._replay_progress_repo.start()

        schema_client = SchemaRegistryClient(url=settings.schema_registry_url)
        self._consumer = KafkaResultConsumer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            topic=settings.results_topic,
            group_id=settings.consumer_group_id,
            schema_client=schema_client,
        )
        await self._consumer.start(self._repo, on_result=on_result)

    @property
    def repo(self) -> AnalysisRepository:
        if not self._repo:
            raise RuntimeError("Factory not started. Call start() first.")
        return self._repo

    @property
    def replay_progress_repo(self) -> ReplayProgressRepository:
        if not self._replay_progress_repo:
            raise RuntimeError("Factory not started. Call start() first.")
        return self._replay_progress_repo

    async def stop(self) -> None:
        if self._consumer:
            await self._consumer.stop()
        if self._replay_progress_repo:
            await self._replay_progress_repo.stop()
        if self._repo:
            await self._repo.stop()
