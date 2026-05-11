from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application Settings
    app_name: str = "BlueprintGuardAIn Analysis Worker"
    log_level: str = "INFO"

    # Kafka Settings
    kafka_bootstrap_servers: str = "localhost:9094"
    webhook_events_topic: str = "webhook-events"
    analysis_results_topic: str = "analysis-results"
    consumer_group_id: str = "analysis-worker-group"

    # Observability
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "analysis-worker"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
