from tests.conftest import a_record

ROUTER = "src.interface.api.router"


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_version(client):
    assert client.get("/version").json() == {
        "service": "dashboard-service",
        "version": "test-sha",
    }


def test_list_curated_repos(client):
    body = client.get("/api/curated-repos").json()
    assert {"repo": "tiangolo/fastapi", "language": "Python"} in body
    assert all({"repo", "language"} == set(item) for item in body)


def test_create_analysis_returns_202(client, mocker):
    mocker.patch(f"{ROUTER}.trigger_analysis", return_value=a_record())

    response = client.post("/api/analyses")

    assert response.status_code == 202
    assert response.json()["id"] == "rec-1"


def test_create_analysis_returns_500_on_failure(client, mocker):
    mocker.patch(f"{ROUTER}.trigger_analysis", side_effect=RuntimeError("github down"))

    response = client.post("/api/analyses")

    assert response.status_code == 500


def test_create_replay_returns_202(client, mocker):
    mocker.patch(f"{ROUTER}.trigger_replay", return_value=a_record())

    response = client.post("/api/replay", json={"repository": "octocat/Hello-World"})

    assert response.status_code == 202


def test_create_replay_requires_repository(client):
    response = client.post("/api/replay", json={"repository": "  "})

    assert response.status_code == 422


def test_create_replay_returns_409_when_exhausted(client, mocker):
    mocker.patch(
        f"{ROUTER}.trigger_replay", side_effect=RuntimeError("All commits replayed")
    )

    response = client.post("/api/replay", json={"repository": "octocat/Hello-World"})

    assert response.status_code == 409


def test_create_replay_returns_500_on_unexpected_error(client, mocker):
    mocker.patch(f"{ROUTER}.trigger_replay", side_effect=ValueError("boom"))

    response = client.post("/api/replay", json={"repository": "octocat/Hello-World"})

    assert response.status_code == 500


def test_list_analyses(client, repo):
    repo.list_all.return_value = [a_record()]

    response = client.get("/api/analyses")

    assert response.status_code == 200
    assert response.json()[0]["repository"] == "octocat/Hello-World"


def test_get_analysis_returns_record(client, repo):
    repo.get.return_value = a_record()

    response = client.get("/api/analyses/rec-1")

    assert response.status_code == 200
    assert response.json()["id"] == "rec-1"


def test_get_analysis_returns_404_when_missing(client, repo):
    repo.get.return_value = None

    response = client.get("/api/analyses/missing")

    assert response.status_code == 404


def test_get_analysis_diff_returns_text(client, repo, mocker):
    repo.get.return_value = a_record()
    mocker.patch(f"{ROUTER}.fetch_commit_diff", return_value="diff --git a/x b/x")

    response = client.get("/api/analyses/rec-1/diff")

    assert response.status_code == 200
    assert response.text == "diff --git a/x b/x"


def test_get_analysis_diff_returns_404_when_record_missing(client, repo):
    repo.get.return_value = None

    response = client.get("/api/analyses/missing/diff")

    assert response.status_code == 404


def test_get_analysis_diff_returns_502_on_github_error(client, repo, mocker):
    repo.get.return_value = a_record()
    mocker.patch(f"{ROUTER}.fetch_commit_diff", side_effect=RuntimeError("gh 500"))

    response = client.get("/api/analyses/rec-1/diff")

    assert response.status_code == 502
