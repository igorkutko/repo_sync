"""Shared dependencies for FastAPI dependency injection."""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from openai import OpenAI

from common.config import Settings
from common.embeddings import EmbeddingClient
from common.qdrant_loader import QdrantLoader

_bearer_scheme = HTTPBearer()


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> None:
    """Validate the Bearer token against the configured API key."""
    if settings.fastapi_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key not configured on server",
        )
    if credentials.credentials != settings.fastapi_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


@lru_cache
def get_qdrant_loader() -> QdrantLoader:
    return QdrantLoader(get_settings())


@lru_cache
def get_embedding_client() -> EmbeddingClient:
    return EmbeddingClient(get_settings())


@lru_cache
def get_openai_client() -> OpenAI:
    return OpenAI(api_key=get_settings().openai_api_key)
