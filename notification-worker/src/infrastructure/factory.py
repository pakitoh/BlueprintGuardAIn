from schema_registry.client import SchemaRegistryClient

from src.config import settings
from src.infrastructure.heartbeat import Heartbeat
from src.infrastructure.kafka.analysis_result_source import KafkaAnalysisResultSource


class InfrastructureFactory:
    def __init__(self) -> None:
        self._schema_client: SchemaRegistryClient | None = None
        self._source: KafkaAnalysisResultSource | None = None
        self._heartbeat: Heartbeat | None = None

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
        self._heartbeat = Heartbeat(
            path=settings.heartbeat_path,
            interval_seconds=settings.heartbeat_interval_seconds,
        )
        await self._heartbeat.start()

        source = KafkaAnalysisResultSource(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            topic=settings.results_topic,
            group_id=settings.consumer_group_id,
            schema_client=self.schema_client,
            dlq_topic=settings.dlq_topic,
        )
        await source.start()
        self._source = source

    async def stop(self) -> None:
        if self._source:
            await self._source.stop()
        if self._heartbeat:
            await self._heartbeat.stop()
