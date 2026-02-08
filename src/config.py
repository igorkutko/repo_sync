"""Application configuration via environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # GitHub
    github_token: str
    github_org_name: str

    # OpenAI
    openai_api_key: str
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4o-mini"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None

    # Sync
    repos_dir: Path = Path("./repos")
    database_url: str = "postgresql://repo_sync:repo_sync@localhost:5432/repo_sync"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Embedding dimensions
    embedding_dimensions: int = 1536

    # Chunking limits
    max_chunk_tokens: int = 6000
    generic_chunk_lines: int = 200
    generic_chunk_overlap: int = 20
