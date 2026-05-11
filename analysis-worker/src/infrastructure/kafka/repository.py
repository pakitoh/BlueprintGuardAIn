import json
from dataclasses import asdict
from aiokafka import AIOKafkaProducer
from src.domain.entities import AnalysisResult
from src.domain.ports import AnalysisRepository


class KafkaAnalysisRepository(AnalysisRepository):
    def __init__(self, producer: AIOKafkaProducer, topic: str):
        self.producer = producer
        self.topic = topic

    async def save(self, result: AnalysisResult) -> None:
        data = asdict(result)
        # Convert datetime to string for JSON serialization
        data["timestamp"] = result.timestamp.isoformat()
        payload = json.dumps(data).encode("utf-8")
        await self.producer.send_and_wait(self.topic, payload)
