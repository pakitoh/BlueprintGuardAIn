import hashlib
import hmac
import json

import pytest

from src.config import settings
from src.domain.exceptions import MappingError
from tests.conftest import WEBHOOK_TEST_SECRET


def a_push_payload():
    return {
        "ref": "refs/heads/main",
        "after": "d4e5f6g7h8",
        "repository": {
            "full_name": "paco/blueprint-guardain",
            "html_url": "https://github.com/paco/blueprint-guardain",
        },
    }


def _sign(body: bytes, secret: str = WEBHOOK_TEST_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _post(client, payload, event="push", signature="valid"):
    """Post a webhook. signature: "valid" signs the body, "bad" sends a wrong
    signature, None omits the header entirely."""
    body = json.dumps(payload).encode()
    headers = {"X-GitHub-Event": event}
    if signature == "valid":
        headers["X-Hub-Signature-256"] = _sign(body)
    elif signature == "bad":
        headers["X-Hub-Signature-256"] = "sha256=deadbeef"
    return client.post("/webhooks/github", content=body, headers=headers)


@pytest.mark.asyncio
async def test_webhook_returns_202_on_success(client, mock_use_case):
    response = _post(client, a_push_payload())
    assert response.status_code == 202
    mock_use_case.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_webhook_passes_event_type_to_use_case(client, mock_use_case):
    response = _post(client, a_push_payload(), event="pull_request")
    assert response.status_code == 202
    _args, kwargs = mock_use_case.execute.call_args
    assert kwargs.get("event_type") == "pull_request"


@pytest.mark.asyncio
async def test_webhook_returns_400_on_mapping_error(client, mock_use_case):
    mock_use_case.execute.side_effect = MappingError("bad payload")
    response = _post(client, a_push_payload())
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_webhook_returns_500_on_unexpected_error(client, mock_use_case):
    mock_use_case.execute.side_effect = RuntimeError("kaboom")
    response = _post(client, a_push_payload())
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_webhook_returns_422_on_validation_error(client, mock_use_case):
    response = _post(client, {"invalid": "payload"})
    assert response.status_code == 422


# --- signature verification ---


@pytest.mark.asyncio
async def test_webhook_rejects_missing_signature(client, mock_use_case):
    response = _post(client, a_push_payload(), signature=None)
    assert response.status_code == 401
    mock_use_case.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_webhook_rejects_bad_signature(client, mock_use_case):
    response = _post(client, a_push_payload(), signature="bad")
    assert response.status_code == 401
    mock_use_case.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_webhook_returns_500_when_secret_not_configured(
    client, mock_use_case, monkeypatch
):
    monkeypatch.setattr(settings, "webhook_secret", "")
    response = _post(client, a_push_payload())
    assert response.status_code == 500
    mock_use_case.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_webhook_preserves_full_raw_payload(client, mock_use_case):
    # a field not declared on GithubWebhookDTO must still reach the use case
    payload = a_push_payload()
    payload["repository"]["owner"] = {"login": "paco"}
    response = _post(client, payload)
    assert response.status_code == 202
    sent_payload, _kwargs = mock_use_case.execute.call_args[0], {}
    assert sent_payload[0]["repository"]["owner"] == {"login": "paco"}
