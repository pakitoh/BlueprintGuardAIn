from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseModel):
    model: str
    api_key: str


class Settings(BaseSettings):
    # Application Settings
    app_name: str = "analysis-worker"
    log_level: str = "INFO"

    # Observability
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9094"
    schema_registry_url: str = "http://localhost:8081"
    webhook_events_topic: str = "webhook-events"
    results_topic: str = "analysis-results"
    consumer_group_id: str = "analysis-worker-group"

    # LLM — first entry is primary, rest are fallbacks
    llm_configs: list[LLMConfig] = []

    # Embeddings — first entry is primary, rest are fallbacks
    embedding_configs: list[LLMConfig] = []

    # GitHub
    github_token: str = ""

    # PostgreSQL / pgvector
    postgres_dsn: str = "postgresql://postgres:postgres@localhost:5432/analysis_db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ANALYSIS_",
        extra="ignore",
    )


settings = Settings()
