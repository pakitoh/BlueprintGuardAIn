from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class AnalysisResult:
    repository: str
    sha: str
    status: str
    findings: List[str]
    timestamp: str
    ingested_at: str | None = None
