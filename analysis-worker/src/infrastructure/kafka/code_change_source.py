import io
import json
import struct
import structlog
from pathlib import Path
from typing import AsyncIterator
from aiokafka import AIOKafkaConsumer
from opentelemetry import context as otel_context
from opentelemetry.propagate import extract
from schema_registry.client import SchemaRegistryClient
from fastavro import schemaless_reader

from src.domain.entities import CodeChange
from src.domain.ports.code_change_source import CodeChangeSource

logger = structlog.get_logger()


class KafkaCodeChangeSource(CodeChangeSource):
    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        group_id: str,
        schema_client: SchemaRegistryClient,
    ):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.group_id = group_id
        self.schema_client = schema_client
        self.consumer = None
        self._schema_cache = {}

    async def start(self):
        self.consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            auto_offset_reset="earliest",
        )
        await self.consumer.start()
        logger.debug("kafka_consumer_started")

    async def stop(self):
        if self.consumer:
            await self.consumer.stop()
            logger.debug("kafka_consumer_stopped")

    def _deserialize_avro(self, payload: bytes) -> dict:
        if len(payload) < 5:
            raise ValueError(f"Payload too short ({len(payload)} bytes).")

        magic, schema_id = struct.unpack(">bi", payload[:5])
        if magic != 0:
            raise ValueError(f"Unknown magic byte: {magic}.")

        if schema_id not in self._schema_cache:
            try:
                avro_schema = self.schema_client.get_by_id(schema_id)
                self._schema_cache[schema_id] = avro_schema.schema
            except Exception as e:
                raise RuntimeError(f"Failed to retrieve schema {schema_id}: {e}")

        bio = io.BytesIO(payload[5:])
        return schemaless_reader(bio, self._schema_cache[schema_id])

    async def listen(self) -> AsyncIterator[CodeChange]:
        if not self.consumer:
            raise RuntimeError("Source not started. Call start() first.")

        async for msg in self.consumer:
            ctx = extract({k: v.decode() for k, v in (msg.headers or [])})
            token = otel_context.attach(ctx)
            try:
                data = self._deserialize_avro(msg.value)
                raw_payload = json.loads(data.get("raw_payload", "{}"))
                yield CodeChange(
                    repository=data.get("repository", "unknown"),
                    ref=data.get("ref", "unknown"),
                    target_sha=data.get("target_sha", "unknown"),
                    event_type=data.get("event_type", "unknown"),
                    raw_payload=raw_payload,
                )
            except Exception as e:
                logger.error("message_consumption_failed", error=str(e))
            finally:
                Path("/tmp/heartbeat").touch()
                otel_context.detach(token)
