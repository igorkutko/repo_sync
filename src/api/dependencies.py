"""Shared dependencies for FastAPI dependency injection."""

from __future__ import annotations

from functools import lru_cache

from openai import OpenAI

from repo_sync.config import Settings
from repo_sync.sync.embeddings import EmbeddingClient
from repo_sync.sync.qdrant_loader import QdrantLoader


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


@lru_cache
def get_qdrant_loader() -> QdrantLoader:
    return QdrantLoader(get_settings())


@lru_cache
def get_embedding_client() -> EmbeddingClient:
    return EmbeddingClient(get_settings())


@lru_cache
def get_openai_client() -> OpenAI:
    return OpenAI(api_key=get_settings().openai_api_key)
