from schema_registry.client import SchemaRegistryClient

from src.config import settings
from src.domain.ports.idempotency_store import IdempotencyStore
from src.infrastructure.idempotency.in_memory_store import InMemoryIdempotencyStore
from src.infrastructure.kafka.repository import KafkaCodeChangeRepository


class InfrastructureFactory:
    def __init__(self) -> None:
        self._schema_client: SchemaRegistryClient | None = None
        self._repo: KafkaCodeChangeRepository | None = None
        # Pure in-memory, no I/O lifecycle — created eagerly and shared across
        # all requests so the dedup cache persists between webhook deliveries.
        self._idempotency_store: IdempotencyStore = InMemoryIdempotencyStore(
            ttl_seconds=settings.webhook_dedup_ttl_seconds
        )

    @property
    def idempotency_store(self) -> IdempotencyStore:
        return self._idempotency_store

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
        with open("../schemas/CodeChange.avsc") as f:
            schema_str = f.read()
        repo = KafkaCodeChangeRepository(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            topic=settings.webhook_events_topic,
            schema_client=self.schema_client,
            schema_str=schema_str,
        )
        await repo.start()
        self._repo = repo

    async def stop(self) -> None:
        if self._repo:
            await self._repo.stop()
