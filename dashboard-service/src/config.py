from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "DASHBOARD_"}

    port: int = 8002
    ingestion_url: str = "http://localhost:8000/webhooks/github"
    kafka_bootstrap_servers: str = "localhost:9094"
    results_topic: str = "analysis-results"
    consumer_group_id: str = "dashboard-service"
    schema_registry_url: str = "http://localhost:8081"
    github_token: str = ""
    postgres_url: str = "postgresql://postgres:postgres@localhost:5432/dashboard_db"


settings = Settings()
