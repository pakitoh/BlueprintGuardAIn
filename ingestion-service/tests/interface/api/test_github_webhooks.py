import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
from src.main import app
from src.interface.api.router import get_process_webhook_use_case
from src.application.use_cases.process_webhook import ProcessWebhookUseCase

@pytest.fixture
def mock_use_case():
    return AsyncMock(spec=ProcessWebhookUseCase)

@pytest.fixture
def client(mock_use_case):
    # Setup the app to use our mock use case
    app.dependency_overrides[get_process_webhook_use_case] = lambda: mock_use_case
    with TestClient(app) as c:
        yield c
    # Clean up overrides
    app.dependency_overrides = {}

def test_webhook_endpoint_success(client, mock_use_case):
    payload = {
        "ref": "refs/heads/main",
        "after": "sha123",
        "repository": {
            "full_name": "paco/repo",
            "html_url": "https://github.com/paco/repo"
        }
    }
    
    headers = {"X-GitHub-Event": "push"}
    response = client.post("/webhooks/github", json=payload, headers=headers)
    
    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    mock_use_case.execute.assert_called_once_with(payload, event_type="push")

def test_webhook_endpoint_unsupported_event(client, mock_use_case):
    # Make the use case raise MappingError to simulate unsupported event logic
    from src.domain.exceptions import MappingError
    mock_use_case.execute.side_effect = MappingError("Unsupported event type")
    
    payload = {
        "repository": {
            "full_name": "paco/repo",
            "html_url": "https://github.com/paco/repo"
        }
    }
    headers = {"X-GitHub-Event": "unsupported"}
    response = client.post("/webhooks/github", json=payload, headers=headers)
    
    assert response.status_code == 400
    assert "Unsupported event type" in response.json()["detail"]
