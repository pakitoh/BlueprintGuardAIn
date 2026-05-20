import pytest
from unittest.mock import AsyncMock, MagicMock
from src.domain.entities import CodeChange
from src.infrastructure.pgvector.pgvector_findings_store import (
    PgVectorFindingsStore,
    _to_embedding_text,
)


def a_change(raw_payload=None):
    return CodeChange(
        repository="org/service",
        ref="refs/heads/main",
        target_sha="sha1",
        event_type="push",
        raw_payload=raw_payload or {},
    )


def a_change_with_commits():
    return a_change(
        raw_payload={
            "commits": [
                {
                    "message": "Add kafka consumer",
                    "added": ["src/infrastructure/kafka/consumer.py"],
                    "modified": [],
                    "removed": [],
                }
            ]
        }
    )


def a_store(pool=None):
    embedder = AsyncMock()
    embedder.embed = AsyncMock(return_value=[0.1] * 768)
    store = PgVectorFindingsStore(dsn="postgresql://unused", embedder=embedder)
    store._pool = pool or AsyncMock()
    return store, embedder


# --- _to_embedding_text ---


def test_embedding_text_strips_repo_name():
    text = _to_embedding_text(a_change_with_commits())
    assert "org/service" not in text


def test_embedding_text_keeps_filename():
    text = _to_embedding_text(a_change_with_commits())
    assert "consumer.py" in text


def test_embedding_text_keeps_layer_segment():
    text = _to_embedding_text(a_change_with_commits())
    assert "kafka" in text


def test_embedding_text_keeps_commit_message():
    text = _to_embedding_text(a_change_with_commits())
    assert "Add kafka consumer" in text


def test_embedding_text_fallback_on_empty_payload():
    text = _to_embedding_text(a_change())
    assert text != ""


# --- find_similar ---


@pytest.mark.asyncio
async def test_find_similar_calls_embed_with_normalized_text():
    store, embedder = a_store()
    store._pool.fetch = AsyncMock(return_value=[])
    await store.find_similar(a_change_with_commits())
    embedder.embed.assert_awaited_once()
    call_text = embedder.embed.call_args[0][0]
    assert "org/service" not in call_text


@pytest.mark.asyncio
async def test_find_similar_returns_past_findings():
    pool = AsyncMock()
    pool.fetch = AsyncMock(
        return_value=[
            {"rule_text": "Use ports not direct imports", "context": "ctx"},
        ]
    )
    store, _ = a_store(pool=pool)
    results = await store.find_similar(a_change_with_commits())
    assert len(results) == 1
    assert results[0].rule_text == "Use ports not direct imports"


@pytest.mark.asyncio
async def test_find_similar_passes_limit_to_query():
    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=[])
    store, _ = a_store(pool=pool)
    await store.find_similar(a_change(), limit=5)
    _, limit_arg = pool.fetch.call_args[0][1], pool.fetch.call_args[0][2]
    assert limit_arg == 5


# --- save ---


@pytest.mark.asyncio
async def test_save_inserts_combined_findings():
    pool = AsyncMock()
    pool.execute = AsyncMock()
    store, _ = a_store(pool=pool)
    await store.save(a_change_with_commits(), ["Finding A", "Finding B"])
    pool.execute.assert_awaited_once()
    sql, rule_text, *_ = pool.execute.call_args[0]
    assert "Finding A" in rule_text
    assert "Finding B" in rule_text


@pytest.mark.asyncio
async def test_save_skips_insert_for_empty_findings():
    pool = AsyncMock()
    pool.execute = AsyncMock()
    store, _ = a_store(pool=pool)
    await store.save(a_change(), [])
    pool.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_save_logs_warning_and_continues_on_error():
    pool = AsyncMock()
    pool.execute = AsyncMock(side_effect=Exception("DB unavailable"))
    store, _ = a_store(pool=pool)
    await store.save(a_change_with_commits(), ["Finding A"])


@pytest.mark.asyncio
async def test_find_similar_returns_empty_list_on_error():
    pool = AsyncMock()
    pool.fetch = AsyncMock(side_effect=Exception("DB unavailable"))
    store, _ = a_store(pool=pool)
    result = await store.find_similar(a_change_with_commits())
    assert result == []
