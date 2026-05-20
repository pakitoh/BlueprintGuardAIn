from difflib import SequenceMatcher

from src.domain.exceptions import DuplicateFindingsError, EmptyFindingsError
from src.domain.ports.diff_fetcher import FileDiff

_SIMILARITY_THRESHOLD = 0.7


class FindingsValidator:
    def validate(self, findings: list[str], diffs: list[FileDiff]) -> None:
        if not findings and diffs:
            raise EmptyFindingsError()
        duplicates = self._find_duplicates(findings)
        if duplicates:
            raise DuplicateFindingsError(duplicates)

    def _find_duplicates(self, findings: list[str]) -> list[tuple[str, str]]:
        pairs = []
        for i, a in enumerate(findings):
            for b in findings[i + 1 :]:
                if SequenceMatcher(None, a.lower(), b.lower()).ratio() >= _SIMILARITY_THRESHOLD:
                    pairs.append((a, b))
        return pairs
