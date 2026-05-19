from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class FileDiff:
    filename: str
    status: str  # added, modified, removed, renamed
    patch: str  # unified diff text; empty for binary files


class DiffFetcher(ABC):
    @abstractmethod
    async def fetch(self, repository: str, sha: str) -> list[FileDiff]:
        """Fetch per-file diffs for a given commit."""
        pass
