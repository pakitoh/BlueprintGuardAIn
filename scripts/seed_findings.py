"""
Seed the past_findings table with curated architectural rules.

Usage (from repo root):
    cd analysis-worker && uv run python -m scripts.seed_findings

Requires ANALYSIS_LLM_API_KEY and optionally ANALYSIS_POSTGRES_DSN to be set.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.config import settings
from src.infrastructure.llm.litellm_embedder import LiteLLMEmbedder
import asyncpg

SEED_ENTRIES = [
    {
        "rule_text": (
            "Kafka consumers must not import concrete infrastructure classes directly. "
            "Use a port (ABC) and inject the dependency via the constructor."
        ),
        "context": "Changed files: kafka/consumer.py\nCommit messages: Add kafka consumer",
    },
    {
        "rule_text": (
            "Domain entities must be pure Python dataclasses or Pydantic models with no "
            "imports from infrastructure or application layers."
        ),
        "context": "Changed files: domain/entities.py\nCommit messages: Add domain entity",
    },
    {
        "rule_text": (
            "Use cases must receive all dependencies (repositories, external services) "
            "via constructor injection. They must never instantiate infrastructure objects."
        ),
        "context": "Changed files: use_cases/process_event.py\nCommit messages: Add use case",
    },
    {
        "rule_text": (
            "Ports (abstract base classes) belong in the domain layer and must contain "
            "only abstract methods. No concrete logic or imports from infrastructure."
        ),
        "context": "Changed files: ports/event_repository.py\nCommit messages: Add port interface",
    },
    {
        "rule_text": (
            "Infrastructure adapters must implement exactly one domain port. "
            "Avoid mixing concerns such as serialization and transport in a single class."
        ),
        "context": "Changed files: infrastructure/kafka/event_repository.py\nCommit messages: Implement Kafka adapter",
    },
    {
        "rule_text": (
            "Kafka producers must serialize messages with Avro using the Confluent Schema Registry. "
            "No raw JSON messages on the wire."
        ),
        "context": "Changed files: infrastructure/kafka/producer.py\nCommit messages: Add Kafka producer",
    },
    {
        "rule_text": (
            "Every Kafka message must include a W3C traceparent header so trace context "
            "is propagated across service boundaries."
        ),
        "context": "Changed files: infrastructure/kafka/producer.py\nCommit messages: Add trace propagation to Kafka",
    },
    {
        "rule_text": (
            "The composition root (main.py) is the only place allowed to wire dependencies. "
            "Use cases and repositories must not import from each other directly."
        ),
        "context": "Changed files: main.py\nCommit messages: Wire dependencies in composition root",
    },
]


async def main() -> None:
    embedder = LiteLLMEmbedder(
        model=settings.embedding_model,
        api_key=settings.llm_api_key,
    )

    pool = await asyncpg.create_pool(settings.postgres_dsn)
    print(f"Connected to {settings.postgres_dsn}")

    inserted = 0
    for entry in SEED_ENTRIES:
        vector = await embedder.embed(entry["context"])
        vector_literal = "[" + ",".join(str(v) for v in vector) + "]"
        await pool.execute(
            """
            INSERT INTO past_findings (rule_text, context, embedding)
            VALUES ($1, $2, $3::vector)
            """,
            entry["rule_text"],
            entry["context"],
            vector_literal,
        )
        inserted += 1
        print(f"  [{inserted}/{len(SEED_ENTRIES)}] {entry['rule_text'][:70]}...")

    await pool.close()
    print(f"\nDone. Inserted {inserted} seed entries.")


if __name__ == "__main__":
    asyncio.run(main())
