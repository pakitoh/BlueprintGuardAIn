import structlog
from typing import List
from litellm import acompletion
from litellm import (
    APIConnectionError,
    BadGatewayError,
    InternalServerError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.domain.analysis_policy import file_priority, should_skip
from src.domain.entities import CodeChange
from src.domain.ports.code_analyzer import CodeAnalyzer
from src.domain.ports.diff_fetcher import DiffFetcher, FileDiff
from src.domain.ports.findings_store import FindingsStore
from src.infrastructure.llm.analyzer_config import (
    INSTRUCTIONS,
    LLM_MAX_ATTEMPTS,
    LLM_TIMEOUT,
    LLM_WAIT_MAX,
    LLM_WAIT_MIN,
    LLM_WAIT_MULTIPLIER,
    NONE_LISTED_PLACEHOLDER,
    NO_PATCH_PLACEHOLDER,
    PAST_FINDINGS_HEADER,
    PATCH_BUDGET,
    PROMPT_TEMPLATE,
    SIZE_WARNING,
    SYSTEM_ROLE,
)

_LLM_RETRYABLE = (
    RateLimitError,
    ServiceUnavailableError,
    APIConnectionError,
    InternalServerError,
    BadGatewayError,
    Timeout,
)

logger = structlog.get_logger()


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

    async def analyze(self, change: CodeChange) -> tuple[List[str], str]:
        try:
            file_diffs = await self._fetch_diffs(change)
            prompt = await self._build_prompt(change, file_diffs)
            raw = await self._call_llm(prompt)
            logger.debug("llm_raw_response", chars=len(raw or ""), preview=(raw or "")[:300])
            findings = self._parse_response(raw)
            logger.info("llm_findings", count=len(findings), findings=findings)
            await self._findings_store.save(change, findings, file_diffs)
            return findings, "COMPLETED"
        except Exception as e:
            logger.error("analysis_failed", error=str(e))
            return [], "FAILED"

    async def _fetch_diffs(self, change: CodeChange) -> list[FileDiff]:
        try:
            return await self._diff_fetcher.fetch(change.repository, change.target_sha)
        except Exception as e:
            logger.warning("diff_fetch_failed", error=str(e))
            return []

    def _select_files_for_review(
        self, file_diffs: list[FileDiff]
    ) -> tuple[list[str], list[str]]:
        """Returns (included_chunks, dropped_filenames) within the patch budget."""
        eligible = sorted(
            [fd for fd in file_diffs if fd.patch and not should_skip(fd.filename)],
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

    async def _build_prompt(
        self, change: CodeChange, file_diffs: list[FileDiff]
    ) -> str:
        included, dropped = self._select_files_for_review(file_diffs)
        examples_section = await self._fetch_examples_section(change, file_diffs)
        prompt = PROMPT_TEMPLATE.format(
            system_role=SYSTEM_ROLE,
            repository=change.repository,
            event_type=change.event_type,
            ref=change.ref,
            sha=change.target_sha,
            patch_section=self._format_patch_section(included),
            size_note=self._format_size_note(dropped),
            messages_section=self._format_messages_section(change),
            examples_section=examples_section,
            instructions=INSTRUCTIONS,
        )
        logger.info(
            "prompt_built",
            repo=change.repository,
            files_included=len(included),
            files_dropped=dropped if dropped else None,
            prompt_chars=len(prompt),
            rag_examples=bool(examples_section),
        )
        return prompt

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

    async def _fetch_examples_section(
        self, change: CodeChange, file_diffs: list[FileDiff]
    ) -> str:
        try:
            similar = await self._findings_store.find_similar(
                change, file_diffs=file_diffs
            )
            if similar:
                logger.info(
                    "rag_examples_found",
                    count=len(similar),
                    rules=[f.rule_text for f in similar],
                )
                items = "\n".join(
                    f"  [{i + 1}] {f.rule_text}" for i, f in enumerate(similar)
                )
                return f"\n{PAST_FINDINGS_HEADER}\n{items}\n"
        except Exception as e:
            logger.warning("findings_store_unavailable", error=str(e))
        return ""

    @retry(
        stop=stop_after_attempt(LLM_MAX_ATTEMPTS),
        wait=wait_exponential(
            multiplier=LLM_WAIT_MULTIPLIER, min=LLM_WAIT_MIN, max=LLM_WAIT_MAX
        ),
        retry=retry_if_exception_type(_LLM_RETRYABLE),
        reraise=True,
        before_sleep=lambda rs: logger.warning(
            "llm_retry", attempt=rs.attempt_number, error=str(rs.outcome.exception())
        ),
    )
    async def _call_llm(self, prompt: str) -> str:
        response = await acompletion(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            api_key=self._api_key,
            timeout=LLM_TIMEOUT,
        )
        return response.choices[0].message.content

    def _parse_response(self, raw: str) -> List[str]:
        if not raw:
            raise ValueError("LLM returned an empty response")
        findings = []
        for line in raw.splitlines():
            line = line.strip().lstrip("-*•").lstrip("0123456789.)").strip()
            if line:
                findings.append(line)
        return findings
