from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application Settings
    app_name: str = "ingestion-service"
    log_level: str = "INFO"
    port: int = 8000

    # Observability
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9094"
    schema_registry_url: str = "http://localhost:8081"
    webhook_events_topic: str = "webhook-events"

    # Security — HMAC secret shared with GitHub for X-Hub-Signature-256
    webhook_secret: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="INGESTION_",
        extra="ignore",
    )


settings = Settings()
