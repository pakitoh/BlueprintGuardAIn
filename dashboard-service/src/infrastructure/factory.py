from schema_registry.client import SchemaRegistryClient

from src.config import settings
from src.domain.ports.analysis_repository import AnalysisRepository
from src.infrastructure.kafka.result_consumer import KafkaResultConsumer
from src.infrastructure.postgres.repository import PostgresAnalysisRepository


class InfrastructureFactory:
    def __init__(self):
        self._consumer: KafkaResultConsumer | None = None
        self._repo: PostgresAnalysisRepository | None = None

    async def start(self) -> None:
        self._repo = PostgresAnalysisRepository(dsn=settings.postgres_url)
        await self._repo.start()

        schema_client = SchemaRegistryClient(url=settings.schema_registry_url)
        self._consumer = KafkaResultConsumer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            topic=settings.results_topic,
            group_id=settings.consumer_group_id,
            schema_client=schema_client,
        )
        await self._consumer.start(self._repo)

    @property
    def repo(self) -> AnalysisRepository:
        if not self._repo:
            raise RuntimeError("Factory not started. Call start() first.")
        return self._repo

    async def stop(self) -> None:
        if self._consumer:
            await self._consumer.stop()
        if self._repo:
            await self._repo.stop()
