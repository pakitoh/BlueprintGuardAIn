from typing import Any

from pydantic import BaseModel


class RepositoryDTO(BaseModel):
    full_name: str
    html_url: str


class CommitDTO(BaseModel):
    id: str
    message: str
    added: list[str] = []
    modified: list[str] = []
    removed: list[str] = []


class PullRequestDTO(BaseModel):
    number: int
    title: str
    head: dict[str, Any]
    base: dict[str, Any]


class GithubWebhookDTO(BaseModel):
    """
    Data Transfer Object for GitHub Webhooks.
    We use Optional fields because the structure varies between
    'push' and 'pull_request'.
    """

    action: str | None = None
    number: int | None = None
    ref: str | None = None
    after: str | None = None
    repository: RepositoryDTO
    commits: list[CommitDTO] = []
    pull_request: PullRequestDTO | None = None
