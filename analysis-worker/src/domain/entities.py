from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class CodeChange:
    repository: str
    ref: str
    target_sha: str
    event_type: str
    raw_payload: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class PastFinding:
    rule_text: str
    context: str


@dataclass(frozen=True)
class LLMResponse:
    content: str
    prompt_tokens: int
    completion_tokens: int
    latency_seconds: float
    cost_usd: float


@dataclass(frozen=True)
class AnalysisResult:
    repository: str
    sha: str
    status: str  # e.g., "COMPLETED", "FAILED"
    findings: list[str]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    ingested_at: datetime | None = None
