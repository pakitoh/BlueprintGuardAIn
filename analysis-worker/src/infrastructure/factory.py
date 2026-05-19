from schema_registry.client import SchemaRegistryClient

from src.config import settings
from src.infrastructure.github.github_diff_fetcher import GitHubDiffFetcher
from src.infrastructure.kafka.analysis_result_repository import (
    KafkaAnalysisResultRepository,
)
from src.infrastructure.kafka.code_change_source import KafkaCodeChangeSource
from src.infrastructure.llm.litellm_code_analyzer import LiteLLMCodeAnalyzer
from src.infrastructure.llm.litellm_embedder import LiteLLMEmbedder
from src.infrastructure.pgvector.pgvector_findings_store import PgVectorFindingsStore


class InfrastructureFactory:
    def __init__(self):
        self._schema_client = None
        self._source = None
        self._sink = None
        self._analyzer = None
        self._embedder = None
        self._findings_store = None

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
    def code_analyzer(self) -> LiteLLMCodeAnalyzer:
        if not self._analyzer:
            raise RuntimeError("Factory not started. Call start() first.")
        return self._analyzer

    async def start(self) -> None:
        self._embedder = LiteLLMEmbedder(
            model=settings.embedding_model,
            api_key=settings.llm_api_key,
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
        with open("../schemas/AnalysisResult.avsc", "r") as f:
            schema_str = f.read()
        self._sink = KafkaAnalysisResultRepository(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            topic=settings.results_topic,
            schema_client=self.schema_client,
            schema_str=schema_str,
        )
        self._analyzer = LiteLLMCodeAnalyzer(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            findings_store=self._findings_store,
            diff_fetcher=GitHubDiffFetcher(token=settings.github_token),
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
