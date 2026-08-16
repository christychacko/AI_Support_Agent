from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLMs -- provider is "groq" or "ollama" per slot, so you can mix and
    # match (e.g. Groq primary + Ollama fallback, or Ollama for both to run
    # fully offline).
    groq_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    primary_provider: str = "groq"
    primary_model: str = "llama-3.1-70b-versatile"

    fallback_provider: str = "groq"
    fallback_model: str = "llama-3.1-8b-instant"

    # Storage
    sqlite_db_path: str = "./data/support.db"
    checkpoint_db_path: str = "./data/checkpoints.sqlite"
    chroma_persist_dir: str = "./data/chroma"

    # Observability
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3001"
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"
    otel_service_name: str = "ai-support-agent"

    # Escalation
    escalation_webhook_url: str = ""

    app_env: str = "development"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
