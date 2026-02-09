"""Search endpoints for code, views, manifests, and cross-collection search."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from qdrant_client.models import FieldCondition, Filter, MatchValue

from api.dependencies import get_embedding_client, get_qdrant_loader, verify_api_key
from api.schemas import (
    CodeSearchRequest,
    ManifestSearchRequest,
    SearchRequest,
    SearchResponse,
    SearchResult,
    ViewSearchRequest,
)
from common.models import CollectionName
from common.embeddings import EmbeddingClient
from common.qdrant_loader import QdrantLoader

router = APIRouter(prefix="/search", tags=["search"], dependencies=[Depends(verify_api_key)])


def _build_filter(conditions: list[tuple[str, str | None]]) -> Filter | None:
    """Build a Qdrant filter from field/value pairs, skipping None values."""
    must = []
    for field, value in conditions:
        if value is not None:
            must.append(FieldCondition(key=field, match=MatchValue(value=value)))
    return Filter(must=must) if must else None


def _search_collection(
    collection: str,
    query_vector: list[float],
    limit: int,
    query_filter: Filter | None,
    loader: QdrantLoader,
) -> list[SearchResult]:
    """Execute a search against a single collection."""
    results = loader.client.query_points(
        collection_name=collection,
        query=query_vector,
        limit=limit,
        query_filter=query_filter,
        with_payload=True,
    )

    search_results = []
    for point in results.points:
        payload = point.payload or {}
        search_results.append(
            SearchResult(
                score=point.score,
                repo_name=payload.get("repo_name", ""),
                module_name=payload.get("module_name", ""),
                file_path=payload.get("file_path", ""),
                chunk_type=payload.get("chunk_type", ""),
                chunk_name=payload.get("chunk_name", ""),
                content=payload.get("content", ""),
                start_line=payload.get("start_line", 0),
                end_line=payload.get("end_line", 0),
                class_name=payload.get("class_name"),
                xml_id=payload.get("xml_id"),
                view_type=payload.get("view_type"),
                view_model=payload.get("view_model"),
                module_category=payload.get("module_category"),
                module_depends=payload.get("module_depends"),
            )
        )
    return search_results


@router.post("/code", response_model=SearchResponse)
def search_code(
    request: CodeSearchRequest,
    loader: QdrantLoader = Depends(get_qdrant_loader),
    embedder: EmbeddingClient = Depends(get_embedding_client),
) -> SearchResponse:
    """Search Python code chunks."""
    query_vector = embedder.embed_query(request.query)
    query_filter = _build_filter([
        ("repo_name", request.repo_name),
        ("module_name", request.module_name),
        ("chunk_type", request.chunk_type),
        ("file_path", request.file_path),
    ])

    results = _search_collection(
        CollectionName.CODE.value, query_vector, request.limit, query_filter, loader
    )
    return SearchResponse(results=results, total=len(results))


@router.post("/views", response_model=SearchResponse)
def search_views(
    request: ViewSearchRequest,
    loader: QdrantLoader = Depends(get_qdrant_loader),
    embedder: EmbeddingClient = Depends(get_embedding_client),
) -> SearchResponse:
    """Search XML views and templates."""
    query_vector = embedder.embed_query(request.query)
    query_filter = _build_filter([
        ("repo_name", request.repo_name),
        ("module_name", request.module_name),
        ("view_type", request.view_type),
        ("view_model", request.view_model),
    ])

    results = _search_collection(
        CollectionName.VIEWS.value, query_vector, request.limit, query_filter, loader
    )
    return SearchResponse(results=results, total=len(results))


@router.post("/manifests", response_model=SearchResponse)
def search_manifests(
    request: ManifestSearchRequest,
    loader: QdrantLoader = Depends(get_qdrant_loader),
    embedder: EmbeddingClient = Depends(get_embedding_client),
) -> SearchResponse:
    """Search module manifests."""
    query_vector = embedder.embed_query(request.query)
    query_filter = _build_filter([
        ("repo_name", request.repo_name),
        ("module_name", request.module_name),
        ("module_category", request.category),
    ])

    results = _search_collection(
        CollectionName.MANIFESTS.value, query_vector, request.limit, query_filter, loader
    )
    return SearchResponse(results=results, total=len(results))


@router.post("/all", response_model=SearchResponse)
def search_all(
    request: SearchRequest,
    loader: QdrantLoader = Depends(get_qdrant_loader),
    embedder: EmbeddingClient = Depends(get_embedding_client),
) -> SearchResponse:
    """Search across all collections, merge results by score."""
    query_vector = embedder.embed_query(request.query)
    query_filter = _build_filter([
        ("repo_name", request.repo_name),
        ("module_name", request.module_name),
    ])

    all_results: list[SearchResult] = []
    for collection in CollectionName:
        results = _search_collection(
            collection.value, query_vector, request.limit, query_filter, loader
        )
        all_results.extend(results)

    # Sort by score descending, take top N
    all_results.sort(key=lambda r: r.score, reverse=True)
    top_results = all_results[: request.limit]

    return SearchResponse(results=top_results, total=len(top_results))
