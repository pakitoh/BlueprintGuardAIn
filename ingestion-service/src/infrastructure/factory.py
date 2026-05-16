from schema_registry.client import SchemaRegistryClient

from src.config import settings
from src.infrastructure.kafka.repository import KafkaCodeChangeRepository


class InfrastructureFactory:
    def __init__(self):
        self._schema_client = None
        self._repo = None

    @property
    def schema_client(self) -> SchemaRegistryClient:
        if self._schema_client is None:
            self._schema_client = SchemaRegistryClient(url=settings.schema_registry_url)
        return self._schema_client

    @property
    def code_change_repository(self) -> KafkaCodeChangeRepository:
        if not self._repo:
            raise RuntimeError("Factory not started. Call start() first.")
        return self._repo

    async def start(self) -> None:
        with open("../schemas/CodeChange.avsc", "r") as f:
            schema_str = f.read()
        self._repo = KafkaCodeChangeRepository(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            topic=settings.webhook_events_topic,
            schema_client=self.schema_client,
            schema_str=schema_str,
        )
        await self._repo.start()

    async def stop(self) -> None:
        if self._repo:
            await self._repo.stop()
