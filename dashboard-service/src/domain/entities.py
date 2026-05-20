from datetime import datetime
from pydantic import BaseModel


class AnalysisRecord(BaseModel):
    id: str
    repository: str
    sha: str
    status: str
    findings: list[str] = []
    created_at: datetime
    completed_at: datetime | None = None
