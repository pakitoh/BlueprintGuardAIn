import json
import asyncio
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
        """Registers the schema with the Registry. Catches connection or registration errors."""
        if self._schema_id is not None:
            return

        try:
            # Register schema with the subject (standard Kafka naming: <topic>-value)
            subject = f"{self.topic}-value"
            self._schema_id = self.schema_client.register(subject, self.schema_str)
            self._parsed_schema = json.loads(self.schema_str)
            logger.debug(
                "kafka_schema_registered", topic=self.topic, schema_id=self._schema_id
            )
        except Exception as e:
            logger.error("schema_registration_failed", error=str(e), topic=self.topic)
            raise RepositoryError(
                f"Failed to register Avro schema for topic {self.topic}: {e}"
            )

    def _serialize_avro(self, data: dict) -> bytes:
        """Encodes data into Avro binary format. Catches validation/encoding errors."""
        try:
            out = io.BytesIO()
            # Confluent Wire Format: Magic byte (0) + 4-byte Schema ID
            out.write(struct.pack(">b", 0))
            out.write(struct.pack(">i", self._schema_id))

            # Binary encoding
            schemaless_writer(out, self._parsed_schema, data)
            return out.getvalue()
        except Exception as e:
            logger.error(
                "avro_serialization_failed", error=str(e), data_keys=list(data.keys())
            )
            raise RepositoryError(f"Failed to serialize data to Avro: {e}")

    async def save(self, code_change: CodeChange) -> None:
        """Serializes the CodeChange and sends it to Kafka with a key."""
        try:
            # 1. Ensure infrastructure is ready
            self._ensure_schema_registered()

            # 2. Prepare and Serialize
            data = asdict(code_change)
            data["raw_payload"] = json.dumps(code_change.raw_payload)
            payload = self._serialize_avro(data)

            # 3. Send with Repository Name as Key for ordering
            key = code_change.repository.encode("utf-8")

            await self.producer.send_and_wait(self.topic, value=payload, key=key)
            logger.info(
                "code_change_sent_to_kafka",
                repo=code_change.repository,
                topic=self.topic,
                schema_id=self._schema_id,
            )

        except RepositoryError:
            raise  # Re-raise our own mapped errors
        except asyncio.TimeoutError as e:
            raise RepositoryError(f"Timeout while sending to Kafka: {e}")
        except Exception as e:
            logger.error("kafka_produce_failed", error=str(e), topic=self.topic)
            raise RepositoryError(f"Failed to save code change to Kafka: {e}")
