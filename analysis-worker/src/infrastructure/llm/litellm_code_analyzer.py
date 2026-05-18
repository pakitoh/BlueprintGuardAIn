import structlog
from typing import List
from litellm import acompletion

from src.domain.entities import CodeChange
from src.domain.ports.code_analyzer import CodeAnalyzer
from src.domain.ports.findings_store import FindingsStore

logger = structlog.get_logger()


class LiteLLMCodeAnalyzer(CodeAnalyzer):
    def __init__(self, model: str, api_key: str, findings_store: FindingsStore):
        self._model = model
        self._api_key = api_key
        self._findings_store = findings_store

    async def analyze(self, change: CodeChange) -> List[str]:
        prompt = await self._build_prompt(change)
        raw = await self._call_llm(prompt)
        findings = self._parse_response(raw)
        try:
            await self._findings_store.save(change, findings)
        except Exception as e:
            logger.warning("findings_save_failed", error=str(e))
        return findings

    async def _build_prompt(self, change: CodeChange) -> str:
        commits = change.raw_payload.get("commits", [])

        files_changed: List[str] = []
        commit_messages: List[str] = []
        for commit in commits:
            files_changed.extend(commit.get("added", []))
            files_changed.extend(commit.get("modified", []))
            files_changed.extend(commit.get("removed", []))
            if msg := commit.get("message"):
                commit_messages.append(msg)

        files_section = (
            "\n".join(f"  - {f}" for f in files_changed) or "  (none listed)"
        )
        messages_section = (
            "\n".join(f"  - {m}" for m in commit_messages) or "  (none listed)"
        )

        examples_section = ""
        try:
            similar = await self._findings_store.find_similar(change)
            if similar:
                items = "\n".join(
                    f"  [{i+1}] {f.rule_text}" for i, f in enumerate(similar)
                )
                examples_section = (
                    f"\nSimilar past findings for reference:\n{items}\n"
                )
        except Exception as e:
            logger.warning("findings_store_unavailable", error=str(e))

        return (
            f"You are an expert software architect reviewing a code change.\n\n"
            f"Repository: {change.repository}\n"
            f"Event: {change.event_type}\n"
            f"Branch: {change.ref}\n"
            f"SHA: {change.target_sha}\n\n"
            f"Changed files:\n{files_section}\n\n"
            f"Commit messages:\n{messages_section}\n"
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
