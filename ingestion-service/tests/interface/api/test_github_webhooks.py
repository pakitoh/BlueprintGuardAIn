REPOSITORY = "user/project"
SHA = "sha123abc"
REF = "refs/heads/main"
EVENT_TYPE = "push"


def test_webhook_endpoint_success(client, mock_use_case):
    payload = {
        "ref": REF,
        "after": SHA,
        "repository": {
            "full_name": REPOSITORY,
            "html_url": f"https://github.com/{REPOSITORY}",
        },
        "commits": [
            {
                "id": SHA,
                "message": "Add feature",
                "added": ["src/new.py"],
                "modified": ["src/existing.py"],
                "removed": [],
            }
        ],
    }
    headers = {"X-GitHub-Event": EVENT_TYPE}

    response = client.post("/webhooks/github", json=payload, headers=headers)

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    called_payload = mock_use_case.execute.call_args[0][0]
    assert called_payload["commits"][0]["added"] == ["src/new.py"]
    assert called_payload["commits"][0]["modified"] == ["src/existing.py"]


def test_webhook_endpoint_unsupported_event(client, mock_use_case):
    # Make the use case raise MappingError to simulate unsupported event logic
    from src.domain.exceptions import MappingError

    mock_use_case.execute.side_effect = MappingError("Unsupported event type")

    payload = {
        "repository": {
            "full_name": REPOSITORY,
            "html_url": f"https://github.com/{REPOSITORY}",
        }
    }
    headers = {"X-GitHub-Event": "unsupported"}

    response = client.post("/webhooks/github", json=payload, headers=headers)

    assert response.status_code == 400
    assert "Unsupported event type" in response.json()["detail"]
