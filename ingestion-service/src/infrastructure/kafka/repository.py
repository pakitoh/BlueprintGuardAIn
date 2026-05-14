import json
import asyncio
from dataclasses import asdict
from aiokafka import AIOKafkaProducer
from src.domain.entities.code_change import CodeChange
from src.domain.ports.repository import CodeChangeRepository
from src.domain.exceptions import RepositoryError


class KafkaCodeChangeRepository(CodeChangeRepository):
    def __init__(self, producer: AIOKafkaProducer, topic: str):
        self.producer = producer
        self.topic = topic

    async def save(self, code_change: CodeChange) -> None:
        """Serializes the CodeChange and sends it to a Kafka topic."""
        try:
            data = asdict(code_change)
            await self.producer.send_and_wait(
                self.topic,
                key=data["repository"].encode("utf-8"),
                value=json.dumps(data).encode("utf-8"),
            )

        except asyncio.TimeoutError as e:
            raise RepositoryError(f"Timeout while sending to Kafka: {e}")
        except Exception as e:
            raise RepositoryError(f"Failed to save code change to Kafka: {e}")
