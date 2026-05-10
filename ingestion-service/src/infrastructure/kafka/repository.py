import json
from dataclasses import asdict
from aiokafka import AIOKafkaProducer
from ...domain.entities.code_change import CodeChange
from ...domain.ports.repository import CodeChangeRepository

class KafkaCodeChangeRepository(CodeChangeRepository):
    def __init__(self, producer: AIOKafkaProducer, topic: str):
        self.producer = producer
        self.topic = topic

    async def save(self, code_change: CodeChange) -> None:
        """Serializes the CodeChange and sends it to a Kafka topic."""
        data = asdict(code_change)
        # Convert the dictionary to JSON bytes
        payload = json.dumps(data).encode("utf-8")
        
        # In aiokafka, we use send_and_wait for simplicity in this TDD phase
        # but in production, we might use background sending.
        await self.producer.send_and_wait(self.topic, payload)
