def test_version_returns_service_name_and_sha(client):
    response = client.get("/version")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "ingestion-service"
    assert body["version"] == "test-sha"
