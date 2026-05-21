import io
import struct
import asyncio
import structlog
from datetime import datetime
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
        self._consumer = None
        self._schema_cache: dict = {}
        self._task = None

    async def start(self, repo: AnalysisRepository) -> None:
        self._consumer = AIOKafkaConsumer(
            self._topic,
            bootstrap_servers=self._bootstrap_servers,
            group_id=self._group_id,
            auto_offset_reset="latest",
        )
        await self._consumer.start()
        self._task = asyncio.create_task(self._consume(repo))
        logger.debug("result_consumer_started")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
        if self._consumer:
            await self._consumer.stop()

    def _deserialize(self, payload: bytes) -> dict:
        magic, schema_id = struct.unpack(">bi", payload[:5])
        if schema_id not in self._schema_cache:
            schema = self._schema_client.get_by_id(schema_id)
            self._schema_cache[schema_id] = schema.schema
        return schemaless_reader(io.BytesIO(payload[5:]), self._schema_cache[schema_id])

    async def _consume(self, repo: AnalysisRepository) -> None:
        async for msg in self._consumer:
            try:
                await self._process_message(msg, repo)
            except Exception as e:
                logger.error("result_consumption_failed", error=str(e))

    async def _process_message(self, msg, repo: AnalysisRepository) -> None:
        data = self._deserialize(msg.value)
        record = await repo.get_by_repo_sha(data["repository"], data["sha"])
        if record:
            await self._apply_result(repo, record, data)

    async def _apply_result(self, repo: AnalysisRepository, record: AnalysisRecord, data: dict) -> None:
        updated = record.model_copy(update={
            "status": data["status"],
            "findings": data.get("findings", []),
            "completed_at": datetime.utcnow(),
        })
        await repo.update(updated)
        logger.info("analysis_completed", id=record.id, findings=len(data.get("findings", [])))
