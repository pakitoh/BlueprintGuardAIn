import json
import io
import struct
import structlog
from dataclasses import asdict
from aiokafka import AIOKafkaProducer
from schema_registry.client import SchemaRegistryClient
from fastavro import schemaless_writer

from src.domain.entities.code_change import CodeChange
from src.domain.ports.repository import CodeChangeRepository
from src.domain.exceptions import RepositoryError

logger = structlog.get_logger()


class KafkaCodeChangeRepository(CodeChangeRepository):
    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        schema_client: SchemaRegistryClient,
        schema_str: str,
    ):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.schema_client = schema_client
        self.schema_str = schema_str
        self.producer = None  # Created in start()
        self._schema_id = None
        self._parsed_schema = None

    async def start(self) -> None:
        """Starts the underlying Kafka producer."""
        try:
            self.producer = AIOKafkaProducer(bootstrap_servers=self.bootstrap_servers)
            await self.producer.start()
            logger.debug("kafka_producer_started", topic=self.topic)
        except Exception as e:
            raise RepositoryError(f"Failed to start Kafka producer: {e}")

    async def stop(self) -> None:
        if self.producer:
            await self.producer.stop()
            logger.debug("kafka_producer_stopped", topic=self.topic)

    def _ensure_schema_registered(self):
        if self._schema_id is not None:
            return
        try:
            subject = f"{self.topic}-value"
            self._schema_id = self.schema_client.register(subject, self.schema_str)
            self._parsed_schema = json.loads(self.schema_str)
        except Exception as e:
            raise RepositoryError(f"Failed to register Avro schema: {e}")

    def _serialize_avro(self, data: dict) -> bytes:
        try:
            out = io.BytesIO()
            out.write(struct.pack(">b", 0))
            out.write(struct.pack(">i", self._schema_id))
            schemaless_writer(out, self._parsed_schema, data)
            return out.getvalue()
        except Exception as e:
            raise RepositoryError(f"Avro serialization failed: {e}")

    async def save(self, code_change: CodeChange) -> None:
        if not self.producer:
            raise RepositoryError("Repository not started. Call start() first.")

        try:
            self._ensure_schema_registered()
            data = asdict(code_change)
            data["raw_payload"] = json.dumps(code_change.raw_payload)
            payload = self._serialize_avro(data)
            key = code_change.repository.encode("utf-8")

            await self.producer.send_and_wait(self.topic, value=payload, key=key)
            logger.info("code_change_sent", repo=code_change.repository)

        except Exception as e:
            logger.error("kafka_produce_failed", error=str(e))
            raise RepositoryError(f"Failed to save code change: {e}")
