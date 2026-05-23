from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisResult:
    repository: str
    sha: str
    status: str
    findings: list[str]
    timestamp: str
    ingested_at: str | None = None
