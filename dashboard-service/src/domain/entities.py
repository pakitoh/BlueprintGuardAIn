from dataclasses import dataclass
from datetime import datetime
from pydantic import BaseModel


@dataclass
class ReplayProgress:
    repository: str
    last_page: int
    current_page: int
    page_index: int


class AnalysisRecord(BaseModel):
    id: str
    repository: str
    sha: str
    status: str
    findings: list[str] = []
    created_at: datetime
    completed_at: datetime | None = None
