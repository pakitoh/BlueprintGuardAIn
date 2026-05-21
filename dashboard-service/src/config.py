from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "dashboard-service"
    log_level: str = "INFO"
    port: int = 8002

    otel_exporter_otlp_endpoint: str = "http://localhost:4317"

    ingestion_url: str = "http://localhost:8000/webhooks/github"
    kafka_bootstrap_servers: str = "localhost:9094"
    results_topic: str = "analysis-results"
    consumer_group_id: str = "dashboard-service"
    schema_registry_url: str = "http://localhost:8081"

    github_token: str = ""
    postgres_url: str = "postgresql://postgres:postgres@localhost:5432/dashboard_db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="DASHBOARD_",
        extra="ignore",
    )


settings = Settings()
