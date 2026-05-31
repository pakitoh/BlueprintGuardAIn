from unittest.mock import MagicMock


def test_read_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_503_when_no_factory(client):
    # test_app does not set app.state.factory
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}


def test_ready_returns_200_when_repository_ready(test_app, client):
    factory = MagicMock()
    factory.code_change_repository.is_ready.return_value = True
    test_app.state.factory = factory

    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_returns_503_when_repository_not_ready(test_app, client):
    factory = MagicMock()
    factory.code_change_repository.is_ready.return_value = False
    test_app.state.factory = factory

    response = client.get("/ready")
    assert response.status_code == 503
