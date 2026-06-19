from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "notification-worker"
    log_level: str = "INFO"

    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_namespace: str = "blueprint-guardain"

    kafka_bootstrap_servers: str = "localhost:9094"
    schema_registry_url: str = "http://localhost:8081"
    results_topic: str = "analysis-results"
    dlq_topic: str = "analysis-results-dlq"
    consumer_group_id: str = "notification-worker-group"

    # Liveness — heartbeat file polled by the container HEALTHCHECK
    heartbeat_path: str = "/tmp/heartbeat"
    heartbeat_interval_seconds: float = 15.0

    github_token: str = ""
    github_api_url: str = "https://api.github.com"
    github_trigger_statuses: list[str] = ["COMPLETED", "FAILED"]

    slack_webhook_url: str = ""
    slack_trigger_statuses: list[str] = ["FAILED"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="NOTIFICATION_",
        extra="ignore",
    )


settings = Settings()
