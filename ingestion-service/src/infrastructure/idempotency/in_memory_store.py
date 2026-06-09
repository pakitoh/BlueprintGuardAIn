import time

from src.domain.ports.idempotency_store import IdempotencyStore


class InMemoryIdempotencyStore(IdempotencyStore):
    """Best-effort, in-process deduplication of already-processed changes.

    Keys are supplied by the caller — the use case keys on ``repository@target_sha``
    — and held for ``ttl_seconds`` so GitHub's retry storms for an already processed
    change are skipped. Not durable: state is lost on restart and is not shared
    across replicas — adequate for the single-instance deployment.
    """

    def __init__(self, ttl_seconds: float):
        self._ttl = ttl_seconds
        self._seen: dict[str, float] = {}

    def is_duplicate(self, key: str) -> bool:
        self._evict_expired()
        return key in self._seen

    def mark_processed(self, key: str) -> None:
        self._seen[key] = time.monotonic() + self._ttl

    def _evict_expired(self) -> None:
        now = time.monotonic()
        for key in [k for k, expiry in self._seen.items() if expiry <= now]:
            del self._seen[key]
