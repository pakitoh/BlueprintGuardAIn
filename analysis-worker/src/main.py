import asyncio
import json
import structlog
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from src.config import settings
from src.infrastructure.observability import setup_observability
from src.infrastructure.kafka.repository import KafkaAnalysisRepository
from src.application.use_cases.analyze_code_change import AnalyzeCodeChangeUseCase
from src.domain.entities import CodeChange

logger = structlog.get_logger()

async def run_worker():
    # Setup Observability
    setup_observability()

    logger.debug("starting_analysis_worker", bootstrap_servers=settings.kafka_bootstrap_servers)

    # Initialize Kafka Producer for results
    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
    await producer.start()

    # Initialize Kafka Consumer for events
    consumer = AIOKafkaConsumer(
        settings.webhook_events_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.consumer_group_id,
        auto_offset_reset="earliest"
    )
    await consumer.start()

    # Initialize Use Case with Kafka Repository
    repository = KafkaAnalysisRepository(producer=producer, topic=settings.analysis_results_topic)
    use_case = AnalyzeCodeChangeUseCase(repository=repository)

    try:
        async for msg in consumer:
            try:
                data = json.loads(msg.value.decode("utf-8"))
                logger.debug("received_message", topic=msg.topic, partition=msg.partition, offset=msg.offset)
                
                # Convert to domain model
                code_change = CodeChange(
                    repository=data.get("repository", "unknown"),
                    ref=data.get("ref", "unknown"),
                    target_sha=data.get("target_sha", "unknown"),
                    event_type=data.get("event_type", "unknown"),
                    raw_payload=data.get("raw_payload", {})
                )

                # Process
                await use_case.execute(code_change)
                
            except Exception as e:
                logger.error("message_processing_failed", error=str(e), offset=msg.offset)
    finally:
        logger.debug("stopping_analysis_worker")
        await consumer.stop()
        await producer.stop()

if __name__ == "__main__":
    asyncio.run(run_worker())
