import structlog
from typing import List

from src.domain.entities import CodeChange, PastFinding
from src.domain.ports.code_analyzer import CodeAnalyzer
from src.domain.ports.diff_fetcher import DiffFetcher, FileDiff
from src.domain.ports.findings_store import FindingsStore
from src.domain.ports.llm_client import LLMClient
from src.application.services.finding_parser import FindingParser
from src.application.services.prompt_composer import PromptComposer

logger = structlog.get_logger()


class LLMCodeAnalyzer(CodeAnalyzer):
    def __init__(
        self,
        llm_client: LLMClient,
        diff_fetcher: DiffFetcher,
        findings_store: FindingsStore,
        prompt_composer: PromptComposer,
        finding_parser: FindingParser,
    ):
        self._llm_client = llm_client
        self._diff_fetcher = diff_fetcher
        self._findings_store = findings_store
        self._prompt_composer = prompt_composer
        self._finding_parser = finding_parser

    async def analyze(self, change: CodeChange) -> tuple[List[str], str]:
        try:
            diffs = await self._fetch_diffs(change)
            past = await self._fetch_past_findings(change, diffs)
            prompt = self._prompt_composer.build(change, diffs, past)
            raw = await self._llm_client.complete(prompt)
            logger.debug("llm_raw_response", chars=len(raw or ""), preview=(raw or "")[:300])
            findings = self._finding_parser.parse(raw)
            logger.info("llm_findings", count=len(findings), findings=findings)
            await self._findings_store.save(change, findings, diffs)
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

    async def _fetch_past_findings(
        self, change: CodeChange, diffs: list[FileDiff]
    ) -> list[PastFinding]:
        try:
            past = await self._findings_store.find_similar(change, file_diffs=diffs)
            if past:
                logger.info(
                    "rag_examples_found",
                    count=len(past),
                    rules=[f.rule_text for f in past],
                )
            return past
        except Exception as e:
            logger.warning("findings_store_unavailable", error=str(e))
            return []
