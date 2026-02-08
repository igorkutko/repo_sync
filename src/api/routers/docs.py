"""Documentation generation endpoint using OpenAI chat completions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAI
from qdrant_client.models import FieldCondition, Filter, MatchValue

from api.dependencies import (
    get_embedding_client,
    get_openai_client,
    get_qdrant_loader,
    get_settings,
    verify_api_key,
)
from api.schemas import DocGenerateRequest, DocGenerateResponse
from config import Settings
from models import CollectionName
from sync.embeddings import EmbeddingClient
from sync.qdrant_loader import QdrantLoader

router = APIRouter(prefix="/docs", tags=["docs"], dependencies=[Depends(verify_api_key)])

DOC_SYSTEM_PROMPT = """You are a technical documentation writer for Odoo modules.
Given code snippets, views, and manifest information from an Odoo module,
generate comprehensive markdown documentation including:
- Module overview and purpose
- Key models and fields
- Business logic (important methods)
- Views and UI components
- Dependencies and configuration
Keep the documentation clear, well-structured, and useful for developers."""


@router.post("/generate", response_model=DocGenerateResponse)
def generate_docs(
    request: DocGenerateRequest,
    loader: QdrantLoader = Depends(get_qdrant_loader),
    embedder: EmbeddingClient = Depends(get_embedding_client),
    openai_client: OpenAI = Depends(get_openai_client),
    settings: Settings = Depends(get_settings),
) -> DocGenerateResponse:
    """Generate markdown documentation for an Odoo module."""
    # Build filter for the specific module
    must_conditions = [
        FieldCondition(
            key="module_name", match=MatchValue(value=request.module_name)
        ),
    ]
    if request.repo_name:
        must_conditions.append(
            FieldCondition(
                key="repo_name", match=MatchValue(value=request.repo_name)
            )
        )
    query_filter = Filter(must=must_conditions)

    # Gather context from all collections
    query_vector = embedder.embed_query(
        f"Odoo module {request.module_name} documentation overview"
    )

    context_parts: list[str] = []
    for collection in CollectionName:
        results = loader.client.query_points(
            collection_name=collection.value,
            query=query_vector,
            limit=20,
            query_filter=query_filter,
            with_payload=True,
        )
        for point in results.points:
            payload = point.payload or {}
            content = payload.get("content", "")
            chunk_type = payload.get("chunk_type", "")
            file_path = payload.get("file_path", "")
            context_parts.append(
                f"--- {chunk_type} from {file_path} ---\n{content}"
            )

    if not context_parts:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for module '{request.module_name}'",
        )

    context = "\n\n".join(context_parts)

    # Generate documentation using chat completions
    response = openai_client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=[
            {"role": "system", "content": DOC_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Generate documentation for the Odoo module '{request.module_name}'.\n\nModule content:\n\n{context}",
            },
        ],
        temperature=0.3,
        max_tokens=4000,
    )

    documentation = response.choices[0].message.content or ""

    return DocGenerateResponse(
        module_name=request.module_name,
        documentation=documentation,
    )
