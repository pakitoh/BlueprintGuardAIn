import structlog
from typing import List
from litellm import acompletion

from src.domain.entities import CodeChange
from src.domain.ports.code_analyzer import CodeAnalyzer

logger = structlog.get_logger()


class LiteLLMCodeAnalyzer(CodeAnalyzer):
    def __init__(self, model: str, api_key: str):
        self._model = model
        self._api_key = api_key

    async def analyze(self, change: CodeChange) -> List[str]:
        prompt = await self._build_prompt(change)
        raw = await self._call_llm(prompt)
        return self._parse_response(raw)

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

        return (
            f"You are an expert software architect reviewing a code change.\n\n"
            f"Repository: {change.repository}\n"
            f"Event: {change.event_type}\n"
            f"Branch: {change.ref}\n"
            f"SHA: {change.target_sha}\n\n"
            f"Changed files:\n{files_section}\n\n"
            f"Commit messages:\n{messages_section}\n\n"
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
