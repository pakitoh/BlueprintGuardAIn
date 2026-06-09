from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.domain.entities import AnalysisRecord
from src.interface.api.router import router


def a_record(status="PENDING", findings=None) -> AnalysisRecord:
    return AnalysisRecord(
        id="rec-1",
        repository="octocat/Hello-World",
        sha="abc123",
        status=status,
        findings=findings or [],
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


@pytest.fixture
def repo():
    return AsyncMock()


@pytest.fixture
def test_app(repo):
    app = FastAPI()
    app.include_router(router)
    app.state.version = "test-sha"
    app.state.repo = repo
    app.state.replay_progress_repo = AsyncMock()
    app.state.replay_page_cache = {}
    app.state.sse_subscribers = set()
    return app


@pytest.fixture
def client(test_app):
    with TestClient(test_app) as c:
        yield c
