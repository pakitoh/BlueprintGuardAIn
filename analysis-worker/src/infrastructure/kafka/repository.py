import json
import io
import struct
import structlog
from dataclasses import asdict
from aiokafka import AIOKafkaProducer
from schema_registry.client import SchemaRegistryClient
from fastavro import schemaless_writer

from src.domain.entities import AnalysisResult
from src.domain.ports import AnalysisRepository
from src.domain.exceptions import (
    RepositoryError,
)  # Assuming this exists or using generic

logger = structlog.get_logger()


class KafkaAnalysisRepository(AnalysisRepository):
    def __init__(
        self,
        producer: AIOKafkaProducer,
        topic: str,
        schema_client: SchemaRegistryClient,
        schema_str: str,
    ):
        self.producer = producer
        self.topic = topic
        self.schema_client = schema_client
        self.schema_str = schema_str
        self._schema_id = None
        self._parsed_schema = None

    def _ensure_schema_registered(self):
        if self._schema_id is not None:
            return

        try:
            subject = f"{self.topic}-value"
            self._schema_id = self.schema_client.register(subject, self.schema_str)
            self._parsed_schema = json.loads(self.schema_str)
            logger.debug(
                "kafka_schema_registered", topic=self.topic, schema_id=self._schema_id
            )
        except Exception as e:
            logger.error("schema_registration_failed", error=str(e), topic=self.topic)
            raise RuntimeError(
                f"Failed to register Avro schema for topic {self.topic}: {e}"
            )

    def _serialize_avro(self, data: dict) -> bytes:
        try:
            out = io.BytesIO()
            out.write(struct.pack(">b", 0))
            out.write(struct.pack(">i", self._schema_id))
            schemaless_writer(out, self._parsed_schema, data)
            return out.getvalue()
        except Exception as e:
            logger.error("avro_serialization_failed", error=str(e))
            raise RuntimeError(f"Failed to serialize data to Avro: {e}")

    async def save(self, result: AnalysisResult) -> None:
        """Serializes the AnalysisResult and sends it to Kafka with a key."""
        try:
            self._ensure_schema_registered()

            # 1. Prepare data (Avro doesn't handle datetime objects natively)
            data = asdict(result)
            data["timestamp"] = result.timestamp.isoformat()

            # 2. Serialize
            payload = self._serialize_avro(data)

            # 3. Send with Repository Name as Key
            key = result.repository.encode("utf-8")

            await self.producer.send_and_wait(self.topic, value=payload, key=key)
            logger.info(
                "analysis_result_sent_to_kafka",
                repo=result.repository,
                topic=self.topic,
                schema_id=self._schema_id,
            )

        except Exception as e:
            logger.error("kafka_produce_failed", error=str(e), topic=self.topic)
            raise e
