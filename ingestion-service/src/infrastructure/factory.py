from schema_registry.client import SchemaRegistryClient

from src.config import settings
from src.infrastructure.kafka.repository import KafkaCodeChangeRepository
from src.domain.ports.repository import CodeChangeRepository


class InfrastructureFactory:
    def __init__(self):
        self._schema_client = None

    @property
    def schema_client(self) -> SchemaRegistryClient:
        if self._schema_client is None:
            self._schema_client = SchemaRegistryClient(url=settings.schema_registry_url)
        return self._schema_client

    def create_code_change_repository(self) -> CodeChangeRepository:
        """Creates a CodeChangeRepository (Infrastructure details hidden)."""
        with open("../schemas/CodeChange.avsc", "r") as f:
            schema_str = f.read()

        return KafkaCodeChangeRepository(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            topic=settings.webhook_events_topic,
            schema_client=self.schema_client,
            schema_str=schema_str,
        )
