"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.dependencies import get_qdrant_loader
from api.schemas import HealthResponse
from sync.qdrant_loader import QdrantLoader

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check(
    loader: QdrantLoader = Depends(get_qdrant_loader),
) -> HealthResponse:
    """Health check with collection statistics."""
    try:
        stats = loader.collection_stats()
        return HealthResponse(status="healthy", collections=stats)
    except Exception:
        return HealthResponse(status="unhealthy", collections={})
