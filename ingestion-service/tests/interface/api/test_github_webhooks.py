import pytest


def test_webhook_endpoint_success(client, mock_use_case):
    payload = {
        "ref": "refs/heads/main",
        "after": "sha123",
        "repository": {
            "full_name": "paco/repo",
            "html_url": "https://github.com/paco/repo",
        },
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
            "html_url": "https://github.com/paco/repo",
        }
    }
    headers = {"X-GitHub-Event": "unsupported"}
    response = client.post("/webhooks/github", json=payload, headers=headers)

    assert response.status_code == 400
    assert "Unsupported event type" in response.json()["detail"]
