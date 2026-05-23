import io
import json
import struct
from dataclasses import asdict
from typing import Any

import structlog
from aiokafka import AIOKafkaProducer
from fastavro import schemaless_writer
from schema_registry.client import SchemaRegistryClient

from src.domain.entities import AnalysisResult
from src.domain.exceptions import RepositoryError
from src.domain.ports.analysis_result_repository import AnalysisResultRepository

logger = structlog.get_logger()


class KafkaAnalysisResultRepository(AnalysisResultRepository):
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
        self.producer: AIOKafkaProducer | None = None  # Created in start()
        self._schema_id: int | None = None
        self._parsed_schema: Any = None

    async def start(self) -> None:
        """Initializes and starts the underlying Kafka producer."""
        try:
            producer = AIOKafkaProducer(bootstrap_servers=self.bootstrap_servers)
            await producer.start()
            self.producer = producer
            logger.debug("kafka_producer_started")
        except Exception as e:
            raise RepositoryError(f"Failed to start Kafka producer: {e}") from e

    async def stop(self) -> None:
        if self.producer:
            await self.producer.stop()
            logger.debug("kafka_producer_stopped")

    def _ensure_schema_registered(self) -> None:
        if self._schema_id is not None:
            return

        try:
            subject = f"{self.topic}-value"
            self._schema_id = self.schema_client.register(subject, self.schema_str)
            self._parsed_schema = json.loads(self.schema_str)
        except Exception as e:
            raise RepositoryError(f"Failed to register Avro schema: {e}") from e

    def _serialize_avro(self, data: dict) -> bytes:
        try:
            out = io.BytesIO()
            out.write(struct.pack(">b", 0))
            out.write(struct.pack(">i", self._schema_id))
            schemaless_writer(out, self._parsed_schema, data)
            return out.getvalue()
        except Exception as e:
            raise RepositoryError(f"Avro serialization failed: {e}") from e

    async def save(self, result: AnalysisResult) -> None:
        if not self.producer:
            raise RepositoryError("Repository not started. Call start() first.")

        try:
            self._ensure_schema_registered()
            data = asdict(result)
            data["timestamp"] = result.timestamp.isoformat()
            data["ingested_at"] = (
                result.ingested_at.isoformat() if result.ingested_at else None
            )
            payload = self._serialize_avro(data)
            key = result.repository.encode("utf-8")

            await self.producer.send_and_wait(self.topic, value=payload, key=key)
            logger.info("analysis_result_sent", repo=result.repository)

        except Exception as e:
            logger.error("kafka_produce_failed", error=str(e))
