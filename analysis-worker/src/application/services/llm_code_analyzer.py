import structlog
from typing import List

from src.domain.entities import CodeChange
from src.domain.exceptions import DuplicateFindingsError, EmptyFindingsError
from src.domain.ports.code_analyzer import CodeAnalyzer
from src.domain.ports.diff_fetcher import DiffFetcher, FileDiff
from src.domain.ports.findings_store import FindingsStore
from src.domain.ports.llm_client import LLMClient
from src.application.services.finding_parser import FindingParser
from src.application.services.findings_validator import FindingsValidator
from src.application.services.prompt_composer import PromptComposer
from src.application.services.prompt_config import (
    MAX_VALIDATION_RETRIES,
    RETRY_DUPLICATE_FINDINGS,
    RETRY_EMPTY_FINDINGS,
)

logger = structlog.get_logger()


class LLMCodeAnalyzer(CodeAnalyzer):
    def __init__(
        self,
        diff_fetcher: DiffFetcher,
        prompt_composer: PromptComposer,
        llm_client: LLMClient,
        findings_store: FindingsStore,
        finding_parser: FindingParser,
        findings_validator: FindingsValidator,
    ):
        self._diff_fetcher = diff_fetcher
        self._prompt_composer = prompt_composer
        self._llm_client = llm_client
        self._findings_store = findings_store
        self._finding_parser = finding_parser
        self._findings_validator = findings_validator

    async def analyze(self, change: CodeChange) -> tuple[List[str], str]:
        try:
            diffs = await self._diff_fetcher.fetch(change.repository, change.target_sha)
            past = await self._findings_store.find_similar(change, file_diffs=diffs)
            prompt = self._prompt_composer.build(change, diffs, past)
            findings = await self._analyze_with_retry(prompt, diffs)
            await self._findings_store.save(change, findings, diffs)
            return findings, "COMPLETED"
        except Exception as e:
            logger.error("analysis_failed", error=str(e))
            return [], "FAILED"

    async def _analyze_with_retry(self, prompt: str, diffs: list[FileDiff]) -> list[str]:
        current_prompt = prompt
        findings: list[str] = []
        for attempt in range(MAX_VALIDATION_RETRIES + 1):
            raw = await self._llm_client.call(current_prompt)
            findings = self._finding_parser.parse(raw)
            try:
                self._findings_validator.validate(findings, diffs)
                return findings
            except EmptyFindingsError:
                logger.warning("llm_empty_findings", attempt=attempt)
                current_prompt = prompt + RETRY_EMPTY_FINDINGS
            except DuplicateFindingsError as e:
                logger.warning("llm_duplicate_findings", attempt=attempt, duplicate_pairs=len(e.pairs))
                current_prompt = prompt + RETRY_DUPLICATE_FINDINGS
        logger.warning("llm_validation_exhausted", final_count=len(findings))
        return findings
