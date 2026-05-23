from schema_registry.client import SchemaRegistryClient

from src.config import settings
from src.infrastructure.kafka.analysis_result_source import KafkaAnalysisResultSource


class InfrastructureFactory:
    def __init__(self) -> None:
        self._schema_client: SchemaRegistryClient | None = None
        self._source: KafkaAnalysisResultSource | None = None

    @property
    def schema_client(self) -> SchemaRegistryClient:
        if self._schema_client is None:
            self._schema_client = SchemaRegistryClient(url=settings.schema_registry_url)
        return self._schema_client

    @property
    def analysis_result_source(self) -> KafkaAnalysisResultSource:
        if not self._source:
            raise RuntimeError("Factory not started. Call start() first.")
        return self._source

    async def start(self) -> None:
        source = KafkaAnalysisResultSource(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            topic=settings.results_topic,
            group_id=settings.consumer_group_id,
            schema_client=self.schema_client,
        )
        await source.start()
        self._source = source

    async def stop(self) -> None:
        if self._source:
            await self._source.stop()
