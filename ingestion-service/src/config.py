from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application Settings
    app_name: str = "BlueprintGuardAIn Ingestion Service"
    log_level: str = "INFO"

    # Kafka Settings
    # Pydantic will automatically look for KAFKA_BOOTSTRAP_SERVERS
    kafka_bootstrap_servers: str = "localhost:9092"
    webhook_events_topic: str = "webhook-events"

    # Pydantic Settings configuration
    # env_file_encoding is useful for cross-platform compatibility
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra env vars
    )


settings = Settings()
