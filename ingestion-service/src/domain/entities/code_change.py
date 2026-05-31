from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.domain.exceptions import MappingError


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class CodeChange:
    """The core domain entity representing a trigger for analysis."""

    repository: str
    ref: str
    target_sha: str
    event_type: str
    raw_payload: dict[str, Any]
    ingested_at: str = field(default_factory=_now_iso)

    def __post_init__(self) -> None:
        if not self.repository:
            raise MappingError("Repository cannot be empty")
        if not self.target_sha:
            raise MappingError("Target SHA cannot be empty")
        if not self.event_type:
            raise MappingError("Event type cannot be empty")

    @classmethod
    def from_push_event(cls, payload: dict[str, Any]) -> "CodeChange":
        """Factory method to create a CodeChange from a GitHub push event."""
        try:
            return cls(
                repository=payload["repository"]["full_name"],
                ref=payload["ref"],
                target_sha=payload["after"],
                event_type="push",
                raw_payload=payload,
            )
        except KeyError as e:
            raise MappingError(f"Missing required field in push event: {e}") from e

    @classmethod
    def from_pull_request_event(cls, payload: dict[str, Any]) -> "CodeChange":
        """Factory method to create a CodeChange from a GitHub pull request event."""
        try:
            return cls(
                repository=payload["repository"]["full_name"],
                ref=f"pr/{payload['number']}",
                target_sha=payload["pull_request"]["head"]["sha"],
                event_type="pull_request",
                raw_payload=payload,
            )
        except KeyError as e:
            raise MappingError(
                f"Missing required field in pull request event: {e}"
            ) from e
