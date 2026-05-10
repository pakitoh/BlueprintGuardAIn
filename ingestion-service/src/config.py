from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    kafka_bootstrap_servers: str = "localhost:9092"
    webhook_events_topic: str = "webhook-events"    
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
