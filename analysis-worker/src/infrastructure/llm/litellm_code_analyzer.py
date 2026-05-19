import structlog
from typing import List
from litellm import acompletion

from src.domain.entities import CodeChange
from src.domain.ports.code_analyzer import CodeAnalyzer
from src.domain.ports.diff_fetcher import DiffFetcher, FileDiff
from src.domain.ports.findings_store import FindingsStore

logger = structlog.get_logger()

_PATCH_BUDGET = 12_000  # ~3k tokens; leaves room for RAG context and response

_SKIP_PATTERNS = frozenset(
    [
        # lock files (all ecosystems)
        ".lock",
        "go.sum",
        # compiled / bytecode
        ".pyc",
        ".class",
        "__pycache__",
        # minified / bundled assets
        ".min.js",
        ".min.css",
        ".bundle.js",
        # build & dependency directories
        "node_modules/",
        "vendor/",
        "dist/",
        "build/",
        "target/",
        # generated code
        ".pb.go",
        "_pb2.py",
        ".generated.",
        "_generated.",
        # test snapshots
        "__snapshots__/",
        ".snap",
        # coverage & CI artefacts
        "lcov.info",
        "coverage.xml",
        ".coverage",
    ]
)

_PRIORITY: dict[str, int] = {
    "domain": 0,
    "ports": 0,
    "application": 1,
    "use_cases": 1,
    "infrastructure": 2,
    "interface": 3,
    "api": 3,
    "test": 4,
    "tests": 4,
}


def _file_priority(filename: str) -> int:
    for part in filename.lower().replace("\\", "/").split("/"):
        if part in _PRIORITY:
            return _PRIORITY[part]
    return 5


def _should_skip(filename: str) -> bool:
    lower = filename.lower()
    return any(p in lower for p in _SKIP_PATTERNS)


class LiteLLMCodeAnalyzer(CodeAnalyzer):
    def __init__(
        self,
        model: str,
        api_key: str,
        findings_store: FindingsStore,
        diff_fetcher: DiffFetcher,
    ):
        self._model = model
        self._api_key = api_key
        self._findings_store = findings_store
        self._diff_fetcher = diff_fetcher

    async def analyze(self, change: CodeChange) -> List[str]:
        try:
            file_diffs = await self._diff_fetcher.fetch(
                change.repository, change.target_sha
            )
        except Exception as e:
            logger.warning("diff_fetch_failed", error=str(e))
            file_diffs = []

        prompt = await self._build_prompt(change, file_diffs)
        raw = await self._call_llm(prompt)
        findings = self._parse_response(raw)
        try:
            await self._findings_store.save(change, findings, file_diffs)
        except Exception as e:
            logger.warning("findings_save_failed", error=str(e))
        return findings

    async def _build_prompt(
        self, change: CodeChange, file_diffs: list[FileDiff]
    ) -> str:
        # filter and sort by architectural priority
        eligible = sorted(
            [fd for fd in file_diffs if fd.patch and not _should_skip(fd.filename)],
            key=lambda fd: _file_priority(fd.filename),
        )

        # fill budget file-by-file — never truncate mid-file
        included: list[str] = []
        dropped: list[str] = []
        budget = _PATCH_BUDGET
        for fd in eligible:
            chunk = f"--- {fd.filename} ({fd.status}) ---\n{fd.patch}\n"
            if len(chunk) <= budget:
                included.append(chunk)
                budget -= len(chunk)
            else:
                dropped.append(fd.filename)

        patch_section = "\n".join(included) if included else "  (no patch available)"
        size_note = ""
        if dropped:
            size_note = (
                f"\n⚠ {len(dropped)} file(s) excluded — PR may be too large for full review. "
                f"Consider splitting the change. Excluded: {', '.join(dropped)}\n"
            )

        commits = change.raw_payload.get("commits", [])
        commit_messages = [c["message"] for c in commits if c.get("message")]
        messages_section = (
            "\n".join(f"  - {m}" for m in commit_messages) or "  (none listed)"
        )

        examples_section = ""
        try:
            similar = await self._findings_store.find_similar(
                change, file_diffs=file_diffs
            )
            if similar:
                items = "\n".join(
                    f"  [{i + 1}] {f.rule_text}" for i, f in enumerate(similar)
                )
                examples_section = f"\nSimilar past findings for reference:\n{items}\n"
        except Exception as e:
            logger.warning("findings_store_unavailable", error=str(e))

        return (
            f"You are an expert software architect reviewing a code change.\n\n"
            f"Repository: {change.repository}\n"
            f"Event: {change.event_type}\n"
            f"Branch: {change.ref}\n"
            f"SHA: {change.target_sha}\n\n"
            f"Commit messages:\n{messages_section}\n\n"
            f"Changed files (diff):\n{patch_section}\n"
            f"{size_note}"
            f"{examples_section}\n"
            f"Provide a concise list of architectural observations, one per line. "
            f"Focus on design patterns, potential issues, coupling, and anything worth flagging in a code review."
        )

    async def _call_llm(self, prompt: str) -> str:
        response = await acompletion(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            api_key=self._api_key,
        )
        return response.choices[0].message.content

    def _parse_response(self, raw: str) -> List[str]:
        findings = []
        for line in raw.splitlines():
            line = line.strip().lstrip("-*•").lstrip("0123456789.)").strip()
            if line:
                findings.append(line)
        return findings
