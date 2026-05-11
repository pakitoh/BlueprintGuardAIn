from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any


@dataclass(frozen=True)
class CodeChange:
    repository: str
    ref: str
    target_sha: str
    event_type: str
    raw_payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class AnalysisResult:
    repository: str
    sha: str
    status: str  # e.g., "COMPLETED", "FAILED"
    findings: str
    timestamp: datetime = field(default_factory=datetime.now)
