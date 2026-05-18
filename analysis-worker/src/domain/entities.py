from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List


@dataclass(frozen=True)
class CodeChange:
    repository: str
    ref: str
    target_sha: str
    event_type: str
    raw_payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class PastFinding:
    rule_text: str
    context: str


@dataclass(frozen=True)
class AnalysisResult:
    repository: str
    sha: str
    status: str  # e.g., "COMPLETED", "FAILED"
    findings: List[str]
    timestamp: datetime = field(default_factory=datetime.now)
    ingested_at: datetime | None = None
