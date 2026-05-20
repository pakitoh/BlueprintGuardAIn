from schema_registry.client import SchemaRegistryClient

from src.config import settings
from src.domain.entities import AnalysisRecord
from src.infrastructure.kafka.result_consumer import KafkaResultConsumer


class InfrastructureFactory:
    def __init__(self):
        self._consumer = None

    async def start(self, store: dict[str, AnalysisRecord]) -> None:
        schema_client = SchemaRegistryClient(url=settings.schema_registry_url)
        self._consumer = KafkaResultConsumer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            topic=settings.results_topic,
            group_id=settings.consumer_group_id,
            schema_client=schema_client,
        )
        await self._consumer.start(store)

    async def stop(self) -> None:
        if self._consumer:
            await self._consumer.stop()
