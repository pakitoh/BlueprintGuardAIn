from dataclasses import dataclass
from typing import Dict, Any
from src.domain.exceptions import MappingError

@dataclass(frozen=True)
class CodeChange:
    """The core domain entity representing a trigger for analysis."""
    repository: str
    ref: str
    target_sha: str
    event_type: str
    raw_payload: Dict[str, Any]

    @classmethod
    def from_push_event(cls, payload: Dict[str, Any]) -> "CodeChange":
        """Factory method to create a CodeChange from a GitHub push event."""
        try:
            return cls(
                repository=payload["repository"]["full_name"],
                ref=payload["ref"],
                target_sha=payload["after"],
                event_type="push",
                raw_payload=payload
            )
        except KeyError as e:
            raise MappingError(f"Missing required field in push event: {e}")

    @classmethod
    def from_pull_request_event(cls, payload: Dict[str, Any]) -> "CodeChange":
        """Factory method to create a CodeChange from a GitHub pull request event."""
        try:
            return cls(
                repository=payload["repository"]["full_name"],
                ref=f"pr/{payload['number']}",
                target_sha=payload["pull_request"]["head"]["sha"],
                event_type="pull_request",
                raw_payload=payload
            )
        except KeyError as e:
            raise MappingError(f"Missing required field in pull request event: {e}")
