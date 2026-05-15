import asyncio
import json
import io
import struct
import structlog
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from opentelemetry import trace
from schema_registry.client import SchemaRegistryClient
from fastavro import schemaless_reader

from src.config import settings
from src.infrastructure.instrumentation import setup_logging, instrument_app
from src.infrastructure.kafka.repository import KafkaAnalysisRepository
from src.application.use_cases.analyze_code_change import AnalyzeCodeChangeUseCase
from src.domain.entities import CodeChange

logger = structlog.get_logger()


# Local cache for parsed Avro schemas to avoid redundant network calls and JSON parsing
SCHEMA_CACHE = {}

def deserialize_avro(payload: bytes, schema_client: SchemaRegistryClient) -> dict:
    """
    Decodes Avro binary format with local caching and robust error handling.
    """
    if len(payload) < 5:
        raise ValueError(f"Payload too short ({len(payload)} bytes). Expected at least 5 bytes for Avro header.")

    # 1. Extract Header (Magic Byte + 4-byte Schema ID)
    try:
        magic, schema_id = struct.unpack(">bi", payload[:5])
    except struct.error as e:
        raise ValueError(f"Malformed Avro header: {e}")

    if magic != 0:
        raise ValueError(f"Unknown magic byte: {magic}. Only Confluent Wire Format (byte 0) is supported.")

    # 2. Get Parsed Schema from Cache or Registry
    if schema_id not in SCHEMA_CACHE:
        try:
            # Registry client returns an AvroSchema object
            avro_schema = schema_client.get_by_id(schema_id)
            # The .schema attribute is already a parsed dictionary
            SCHEMA_CACHE[schema_id] = avro_schema.schema
            logger.debug("schema_cached", schema_id=schema_id)
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve/parse schema {schema_id} from registry: {e}")

    # 3. Decode binary data using the cached schema
    try:
        bio = io.BytesIO(payload[5:])
        return schemaless_reader(bio, SCHEMA_CACHE[schema_id])
    except Exception as e:
        raise ValueError(f"Avro decoding failed for schema {schema_id}: {e}")


async def run_worker():
    # Setup OTEL Tracing & Metrics
    instrument_app()

    logger.debug(
        "starting_analysis_worker", bootstrap_servers=settings.kafka_bootstrap_servers
    )

    # Initialize Schema Registry Client
    schema_client = SchemaRegistryClient(url=settings.schema_registry_url)

    # Load Schemas
    with open("../schemas/CodeChange.avsc", "r") as f:
        code_change_schema = f.read()
    with open("../schemas/AnalysisResult.avsc", "r") as f:
        analysis_result_schema = f.read()

    # Initialize Kafka Producer for results
    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
    await producer.start()

    # Initialize Kafka Consumer for events
    consumer = AIOKafkaConsumer(
        settings.webhook_events_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.consumer_group_id,
        auto_offset_reset="earliest",
    )
    await consumer.start()

    # Initialize Use Case with Kafka Repository
    repository = KafkaAnalysisRepository(
        producer=producer,
        topic=settings.results_topic,
        schema_client=schema_client,
        schema_str=analysis_result_schema,
    )
    use_case = AnalyzeCodeChangeUseCase(repository=repository)

    tracer = trace.get_tracer(__name__)

    try:
        async for msg in consumer:
            with tracer.start_as_current_span(
                "process_kafka_message",
                attributes={
                    "messaging.system": "kafka",
                    "messaging.destination": msg.topic,
                    "messaging.kafka.partition": msg.partition,
                },
            ):
                try:
                    # 1. Deserialize Avro Payload
                    data = deserialize_avro(msg.value, schema_client)
                    logger.debug(
                        "received_message",
                        topic=msg.topic,
                        partition=msg.partition,
                        offset=msg.offset,
                    )

                    # 2. Convert to domain model
                    # raw_payload is stored as stringified JSON in Avro, decode it back to dict
                    raw_payload = json.loads(data.get("raw_payload", "{}"))

                    code_change = CodeChange(
                        repository=data.get("repository", "unknown"),
                        ref=data.get("ref", "unknown"),
                        target_sha=data.get("target_sha", "unknown"),
                        event_type=data.get("event_type", "unknown"),
                        raw_payload=raw_payload,
                    )

                    # 3. Process
                    await use_case.execute(code_change)

                except Exception as e:
                    logger.error(
                        "message_processing_failed", error=str(e), offset=msg.offset
                    )
    finally:
        logger.debug("stopping_analysis_worker")
        await consumer.stop()
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(run_worker())
