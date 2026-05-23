import io
import struct
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, cast

import structlog
from aiokafka import AIOKafkaConsumer
from fastavro import schemaless_reader
from opentelemetry import context as otel_context
from opentelemetry.propagate import extract
from schema_registry.client import SchemaRegistryClient

from src.domain.entities import AnalysisResult
from src.domain.ports.analysis_result_source import AnalysisResultSource

logger = structlog.get_logger()


class KafkaAnalysisResultSource(AnalysisResultSource):
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
        self.consumer: AIOKafkaConsumer | None = None
        self._schema_cache: dict[int, Any] = {}

    async def start(self) -> None:
        self.consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            auto_offset_reset="earliest",
        )
        await self.consumer.start()
        logger.debug("kafka_consumer_started")

    async def stop(self) -> None:
        if self.consumer:
            await self.consumer.stop()
            logger.debug("kafka_consumer_stopped")

    def _deserialize_avro(self, payload: bytes) -> dict[str, Any]:
        if len(payload) < 5:
            raise ValueError(f"Payload too short ({len(payload)} bytes).")

        magic, schema_id = struct.unpack(">bi", payload[:5])
        if magic != 0:
            raise ValueError(f"Unknown magic byte: {magic}.")

        if schema_id not in self._schema_cache:
            try:
                avro_schema = self.schema_client.get_by_id(schema_id)
                if avro_schema is None:
                    raise RuntimeError(f"Schema {schema_id} not found in registry.")
                self._schema_cache[schema_id] = avro_schema.schema
            except Exception as e:
                raise RuntimeError(f"Failed to retrieve schema {schema_id}: {e}") from e

        bio = io.BytesIO(payload[5:])
        parsed = schemaless_reader(bio, self._schema_cache[schema_id])
        return cast(dict[str, Any], parsed)

    async def listen(self) -> AsyncIterator[AnalysisResult]:
        if not self.consumer:
            raise RuntimeError("Source not started. Call start() first.")

        async for msg in self.consumer:
            ctx = extract({k: v.decode() for k, v in (msg.headers or [])})
            token = otel_context.attach(ctx)
            try:
                data = self._deserialize_avro(msg.value)
                yield AnalysisResult(
                    repository=data["repository"],
                    sha=data["sha"],
                    status=data["status"],
                    findings=list(data["findings"]),
                    timestamp=data["timestamp"],
                    ingested_at=data.get("ingested_at"),
                )
            except Exception as e:
                logger.error("message_consumption_failed", error=str(e))
            finally:
                Path("/tmp/heartbeat").touch()
                otel_context.detach(token)
