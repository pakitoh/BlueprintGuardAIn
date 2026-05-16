from schema_registry.client import SchemaRegistryClient

from src.config import settings
from src.application.use_cases.analyze_code_change import AnalyzeCodeChangeUseCase
from src.infrastructure.kafka.analysis_result_repository import (
    KafkaAnalysisResultRepository,
)
from src.infrastructure.kafka.code_change_repository import KafkaCodeChangeRepository
from src.infrastructure.tracing.instrumented_analyze_code_change import (
    InstrumentedAnalyzeCodeChangeUseCase,
)
from src.domain.ports.analysis_result_repository import AnalysisResultRepository
from src.domain.ports.code_change_repository import CodeChangeRepository


class InfrastructureFactory:
    def __init__(self):
        self._schema_client = None

    @property
    def schema_client(self) -> SchemaRegistryClient:
        if self._schema_client is None:
            self._schema_client = SchemaRegistryClient(url=settings.schema_registry_url)
        return self._schema_client

    def create_analysis_result_repository(self) -> AnalysisResultRepository:
        with open("../schemas/AnalysisResult.avsc", "r") as f:
            schema_str = f.read()

        return KafkaAnalysisResultRepository(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            topic=settings.results_topic,
            schema_client=self.schema_client,
            schema_str=schema_str,
        )

    def create_code_change_repository(self) -> CodeChangeRepository:
        return KafkaCodeChangeRepository(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            topic=settings.webhook_events_topic,
            group_id=settings.consumer_group_id,
            schema_client=self.schema_client,
        )

    def create_analyze_code_change_use_case(
        self, source: CodeChangeRepository, sink: AnalysisResultRepository
    ) -> AnalyzeCodeChangeUseCase:
        return InstrumentedAnalyzeCodeChangeUseCase(source=source, sink=sink)
