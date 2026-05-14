from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application Settings
    app_name: str = "analysis-worker"
    log_level: str = "INFO"

    # Observability
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9094"
    webhook_events_topic: str = "webhook-events"
    results_topic: str = "analysis-results"
    consumer_group_id: str = "analysis-worker-group"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ANALYSIS_",
        extra="ignore",
    )


settings = Settings()
