#!/usr/bin/env python3
# /// script
# dependencies = [
#   "aiokafka",
#   "fastavro",
#   "python-schema-registry-client",
# ]
# ///

# Injects malformed/mismatched-schema messages into a Kafka topic to simulate
# the kind of breakage real teams hit in production (a bad deploy publishing
# garbage bytes, or a producer drifting onto the wrong schema).
#
# Usage:
#   uv run scripts/chaos_kafka.py --mode garbage --count 5
#   uv run scripts/chaos_kafka.py --mode truncated --topic webhook-events
#   uv run scripts/chaos_kafka.py --mode wrong-schema --count 3

import argparse
import asyncio
import io
import json
import random
import struct
import time
import uuid

from aiokafka import AIOKafkaProducer
from fastavro import schemaless_writer
from schema_registry.client import SchemaRegistryClient

KAFKA_BOOTSTRAP_SERVERS = "localhost:9094"
SCHEMA_REGISTRY_URL = "http://localhost:8081"

CODE_CHANGE_TOPIC = "webhook-events"
ANALYSIS_RESULT_TOPIC = "analysis-results"

# Schemas mirror schemas/CodeChange.avsc and schemas/AnalysisResult.avsc
CODE_CHANGE_SCHEMA = {
    "type": "record",
    "name": "CodeChange",
    "namespace": "com.blueprint.guardain",
    "fields": [
        {"name": "repository", "type": "string"},
        {"name": "ref", "type": "string"},
        {"name": "target_sha", "type": "string"},
        {"name": "event_type", "type": "string"},
        {"name": "raw_payload", "type": "string"},
        {"name": "ingested_at", "type": ["null", "string"], "default": None},
    ],
}

ANALYSIS_RESULT_SCHEMA = {
    "type": "record",
    "name": "AnalysisResult",
    "namespace": "com.blueprint.guardain",
    "fields": [
        {"name": "repository", "type": "string"},
        {"name": "sha", "type": "string"},
        {"name": "status", "type": "string"},
        {"name": "findings", "type": {"type": "array", "items": "string"}},
        {"name": "timestamp", "type": "string"},
        {"name": "ingested_at", "type": ["null", "string"], "default": None},
    ],
}


def _avro_envelope(schema_id: int, schema: dict, data: dict) -> bytes:
    """Builds the Confluent wire format: magic byte + schema id + Avro body."""
    out = io.BytesIO()
    out.write(struct.pack(">b", 0))
    out.write(struct.pack(">i", schema_id))
    schemaless_writer(out, schema, data)
    return out.getvalue()


def build_garbage_payload() -> bytes:
    """Random bytes with no valid magic byte — fails before schema lookup."""
    return bytes(random.randint(0, 255) for _ in range(random.randint(5, 40)))


def build_truncated_payload(schema_id: int) -> bytes:
    """A real envelope cut short mid-record — fails inside the Avro reader."""
    full = _avro_envelope(
        schema_id,
        CODE_CHANGE_SCHEMA,
        {
            "repository": "acme/widgets",
            "ref": "refs/heads/main",
            "target_sha": uuid.uuid4().hex,
            "event_type": "push",
            "raw_payload": "{}",
            "ingested_at": None,
        },
    )
    return full[: max(6, len(full) // 2)]


def build_wrong_schema_payload(schema_id: int) -> bytes:
    """A validly-encoded AnalysisResult record, published to webhook-events.

    Decodes successfully (it's valid Avro), but the consumer reads it as a
    CodeChange — only the shared field (`repository`) survives, everything
    else silently falls back to "unknown" instead of raising.
    """
    return _avro_envelope(
        schema_id,
        ANALYSIS_RESULT_SCHEMA,
        {
            "repository": "acme/widgets",
            "sha": uuid.uuid4().hex,
            "status": "completed",
            "findings": ["looks fine"],
            "timestamp": "2026-06-19T00:00:00+00:00",
            "ingested_at": None,
        },
    )


async def send_chaos_message(
    producer: AIOKafkaProducer,
    schema_client: SchemaRegistryClient,
    mode: str,
    topic: str,
) -> None:
    key = b"acme/widgets"

    if mode == "garbage":
        payload = build_garbage_payload()
    elif mode == "truncated":
        schema_id = schema_client.register(f"{CODE_CHANGE_TOPIC}-value", json.dumps(CODE_CHANGE_SCHEMA))
        payload = build_truncated_payload(schema_id)
    elif mode == "wrong-schema":
        schema_id = schema_client.register(
            f"{ANALYSIS_RESULT_TOPIC}-value", json.dumps(ANALYSIS_RESULT_SCHEMA)
        )
        payload = build_wrong_schema_payload(schema_id)
    else:
        raise ValueError(f"Unknown mode: {mode}")

    await producer.send_and_wait(topic, value=payload, key=key)
    print(f"→ [{time.strftime('%H:%M:%S')}] sent {mode} message ({len(payload)} bytes) to {topic}")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inject malformed/mismatched-schema messages into Kafka."
    )
    parser.add_argument(
        "--mode",
        choices=["garbage", "truncated", "wrong-schema"],
        default="garbage",
        help="garbage = random bytes, truncated = cut-short Avro record, "
        "wrong-schema = valid AnalysisResult record sent as CodeChange (default: garbage)",
    )
    parser.add_argument(
        "--topic", default=CODE_CHANGE_TOPIC,
        help=f"Target topic (default: {CODE_CHANGE_TOPIC})",
    )
    parser.add_argument("--count", type=int, default=1, help="Number of messages to send (default: 1)")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between messages (default: 1.0)")
    args = parser.parse_args()

    schema_client = SchemaRegistryClient(SCHEMA_REGISTRY_URL)
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
    await producer.start()

    print("=== Kafka Chaos Injector ===")
    print(f"Mode  : {args.mode}")
    print(f"Topic : {args.topic}")
    print(f"Count : {args.count}")
    print("=============================")

    try:
        for _ in range(args.count):
            await send_chaos_message(producer, schema_client, args.mode, args.topic)
            await asyncio.sleep(args.delay)
    finally:
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(main())
