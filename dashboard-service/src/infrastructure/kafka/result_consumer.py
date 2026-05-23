import asyncio
import io
import struct
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any, cast

import structlog
from aiokafka import AIOKafkaConsumer
from fastavro import schemaless_reader
from schema_registry.client import SchemaRegistryClient

from src.domain.entities import AnalysisRecord
from src.domain.ports.analysis_repository import AnalysisRepository

logger = structlog.get_logger()


class KafkaResultConsumer:
    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        group_id: str,
        schema_client: SchemaRegistryClient,
    ):
        self._bootstrap_servers = bootstrap_servers
        self._topic = topic
        self._group_id = group_id
        self._schema_client = schema_client
        self._consumer: AIOKafkaConsumer | None = None
        self._schema_cache: dict[int, Any] = {}
        self._task: asyncio.Task[None] | None = None
        self._on_result: Callable[[AnalysisRecord], Awaitable[None]] | None = None

    async def start(
        self,
        repo: AnalysisRepository,
        on_result: Callable[[AnalysisRecord], Awaitable[None]] | None = None,
    ) -> None:
        self._on_result = on_result
        consumer = AIOKafkaConsumer(
            self._topic,
            bootstrap_servers=self._bootstrap_servers,
            group_id=self._group_id,
            auto_offset_reset="latest",
        )
        await consumer.start()
        self._consumer = consumer
        self._task = asyncio.create_task(self._consume(repo))
        logger.debug("result_consumer_started")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
        if self._consumer:
            await self._consumer.stop()

    def _deserialize(self, payload: bytes) -> dict[str, Any]:
        _magic, schema_id = struct.unpack(">bi", payload[:5])
        if schema_id not in self._schema_cache:
            schema = self._schema_client.get_by_id(schema_id)
            if schema is None:
                raise RuntimeError(f"Schema {schema_id} not found in registry.")
            self._schema_cache[schema_id] = schema.schema
        bio = io.BytesIO(payload[5:])
        parsed = schemaless_reader(bio, self._schema_cache[schema_id])
        return cast(dict[str, Any], parsed)

    async def _consume(self, repo: AnalysisRepository) -> None:
        assert self._consumer is not None
        async for msg in self._consumer:
            try:
                await self._process_message(msg, repo)
            except Exception as e:
                logger.error("result_consumption_failed", error=str(e))

    async def _process_message(self, msg: Any, repo: AnalysisRepository) -> None:
        data = self._deserialize(msg.value)
        record = await repo.get_by_repo_sha(data["repository"], data["sha"])
        if record:
            await self._apply_result(repo, record, data)

    async def _apply_result(
        self, repo: AnalysisRepository, record: AnalysisRecord, data: dict
    ) -> None:
        updated = record.model_copy(
            update={
                "status": data["status"],
                "findings": data.get("findings", []),
                "completed_at": datetime.utcnow(),
            }
        )
        await repo.update(updated)
        if self._on_result:
            await self._on_result(updated)
        logger.info(
            "analysis_completed", id=record.id, findings=len(data.get("findings", []))
        )
