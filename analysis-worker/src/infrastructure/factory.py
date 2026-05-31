from langfuse import get_client
from schema_registry.client import SchemaRegistryClient

from src.application.services.finding_parser import FindingParser
from src.application.services.findings_validator import FindingsValidator
from src.application.services.llm_code_analyzer import LLMCodeAnalyzer
from src.application.services.prompt_composer import PromptComposer
from src.config import settings
from src.infrastructure.github.github_diff_fetcher import GitHubDiffFetcher
from src.infrastructure.heartbeat import Heartbeat
from src.infrastructure.instrumentation import flush_langfuse
from src.infrastructure.kafka.analysis_result_repository import (
    KafkaAnalysisResultRepository,
)
from src.infrastructure.kafka.code_change_source import KafkaCodeChangeSource
from src.infrastructure.langfuse.prompt_repository import LangfusePromptRepository
from src.infrastructure.llm.litellm_client import LiteLLMClient
from src.infrastructure.llm.litellm_embedder import LiteLLMEmbedder
from src.infrastructure.pgvector.pgvector_findings_store import PgVectorFindingsStore


class InfrastructureFactory:
    def __init__(self) -> None:
        self._schema_client: SchemaRegistryClient | None = None
        self._source: KafkaCodeChangeSource | None = None
        self._sink: KafkaAnalysisResultRepository | None = None
        self._analyzer: LLMCodeAnalyzer | None = None
        self._embedder: LiteLLMEmbedder | None = None
        self._findings_store: PgVectorFindingsStore | None = None
        self._heartbeat: Heartbeat | None = None

    @property
    def schema_client(self) -> SchemaRegistryClient:
        if self._schema_client is None:
            self._schema_client = SchemaRegistryClient(url=settings.schema_registry_url)
        return self._schema_client

    @property
    def code_change_source(self) -> KafkaCodeChangeSource:
        if not self._source:
            raise RuntimeError("Factory not started. Call start() first.")
        return self._source

    @property
    def analysis_result_repository(self) -> KafkaAnalysisResultRepository:
        if not self._sink:
            raise RuntimeError("Factory not started. Call start() first.")
        return self._sink

    @property
    def code_analyzer(self) -> LLMCodeAnalyzer:
        if not self._analyzer:
            raise RuntimeError("Factory not started. Call start() first.")
        return self._analyzer

    async def start(self) -> None:
        self._heartbeat = Heartbeat(
            path=settings.heartbeat_path,
            interval_seconds=settings.heartbeat_interval_seconds,
        )
        await self._heartbeat.start()

        if not settings.llm_configs:
            raise RuntimeError("ANALYSIS_LLM_CONFIGS must have at least one entry")
        if not settings.embedding_configs:
            raise RuntimeError(
                "ANALYSIS_EMBEDDING_CONFIGS must have at least one entry"
            )

        self._embedder = LiteLLMEmbedder(
            configs=[(c.model, c.api_key) for c in settings.embedding_configs],
        )
        self._findings_store = PgVectorFindingsStore(
            dsn=settings.postgres_dsn,
            embedder=self._embedder,
        )
        await self._findings_store.start()

        self._source = KafkaCodeChangeSource(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            topic=settings.webhook_events_topic,
            group_id=settings.consumer_group_id,
            schema_client=self.schema_client,
        )
        with open("../schemas/AnalysisResult.avsc") as f:
            schema_str = f.read()
        self._sink = KafkaAnalysisResultRepository(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            topic=settings.results_topic,
            schema_client=self.schema_client,
            schema_str=schema_str,
        )
        prompt_repo = LangfusePromptRepository(
            client=get_client(),
            prompt_name=settings.langfuse_prompt_name,
            cache_ttl_seconds=settings.langfuse_prompt_cache_ttl_seconds,
        )
        self._analyzer = LLMCodeAnalyzer(
            diff_fetcher=GitHubDiffFetcher(token=settings.github_token),
            prompt_composer=PromptComposer(prompt_repo),
            llm_client=LiteLLMClient(
                configs=[(c.model, c.api_key) for c in settings.llm_configs],
            ),
            findings_store=self._findings_store,
            finding_parser=FindingParser(),
            findings_validator=FindingsValidator(),
        )
        await self._source.start()
        await self._sink.start()

    async def stop(self) -> None:
        if self._sink:
            await self._sink.stop()
        if self._source:
            await self._source.stop()
        if self._findings_store:
            await self._findings_store.stop()
        if self._heartbeat:
            await self._heartbeat.stop()
        flush_langfuse()
