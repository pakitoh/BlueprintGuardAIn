from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class RepositoryDTO(BaseModel):
    full_name: str
    html_url: str

class PullRequestDTO(BaseModel):
    number: int
    title: str
    head: Dict[str, Any]
    base: Dict[str, Any]

class GithubWebhookDTO(BaseModel):
    """
    Data Transfer Object for GitHub Webhooks.
    We use Optional fields because the structure varies between 'push' and 'pull_request'.
    """
    action: Optional[str] = None
    number: Optional[int] = None
    ref: Optional[str] = None
    after: Optional[str] = None
    repository: RepositoryDTO
    pull_request: Optional[PullRequestDTO] = None
