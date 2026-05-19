import structlog

from src.domain.analysis_policy import file_priority, should_skip
from src.domain.entities import CodeChange, PastFinding
from src.domain.ports.diff_fetcher import FileDiff
from src.application.services.prompt_config import (
    INSTRUCTIONS,
    NONE_LISTED_PLACEHOLDER,
    NO_PATCH_PLACEHOLDER,
    PAST_FINDINGS_HEADER,
    PATCH_BUDGET,
    PROMPT_TEMPLATE,
    SIZE_WARNING,
    SYSTEM_ROLE,
)

logger = structlog.get_logger()


class PromptComposer:
    def build(
        self,
        change: CodeChange,
        diffs: list[FileDiff],
        past: list[PastFinding],
    ) -> str:
        included, dropped = self._select_files_for_review(diffs)
        prompt = PROMPT_TEMPLATE.format(
            system_role=SYSTEM_ROLE,
            repository=change.repository,
            event_type=change.event_type,
            ref=change.ref,
            sha=change.target_sha,
            patch_section=self._format_patch_section(included),
            size_note=self._format_size_note(dropped),
            messages_section=self._format_messages_section(change),
            examples_section=self._format_examples_section(past),
            instructions=INSTRUCTIONS,
        )
        logger.info(
            "prompt_built",
            repo=change.repository,
            files_included=len(included),
            files_dropped=dropped if dropped else None,
            prompt_chars=len(prompt),
            rag_examples=bool(past),
        )
        return prompt

    def _select_files_for_review(
        self, diffs: list[FileDiff]
    ) -> tuple[list[str], list[str]]:
        eligible = sorted(
            [fd for fd in diffs if fd.patch and not should_skip(fd.filename)],
            key=lambda fd: file_priority(fd.filename),
        )
        included: list[str] = []
        dropped: list[str] = []
        budget = PATCH_BUDGET
        for fd in eligible:
            chunk = f"--- {fd.filename} ({fd.status}) ---\n{fd.patch}\n"
            if len(chunk) <= budget:
                included.append(chunk)
                budget -= len(chunk)
            else:
                dropped.append(fd.filename)
        return included, dropped

    def _format_patch_section(self, included: list[str]) -> str:
        content = "\n".join(included).rstrip("\n") if included else NO_PATCH_PLACEHOLDER
        return content + "\n"

    def _format_size_note(self, dropped: list[str]) -> str:
        if not dropped:
            return ""
        return SIZE_WARNING.format(count=len(dropped), files=", ".join(dropped))

    def _format_messages_section(self, change: CodeChange) -> str:
        commits = change.raw_payload.get("commits", [])
        messages = [c["message"] for c in commits if c.get("message")]
        return "\n".join(f"  - {m}" for m in messages) or NONE_LISTED_PLACEHOLDER

    def _format_examples_section(self, past: list[PastFinding]) -> str:
        if not past:
            return ""
        items = "\n".join(f"  [{i + 1}] {f.rule_text}" for i, f in enumerate(past))
        return f"\n{PAST_FINDINGS_HEADER}\n{items}\n"
