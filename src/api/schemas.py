"""Request and response Pydantic models for the API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., description="Natural language search query")
    limit: int = Field(default=10, ge=1, le=50, description="Max results to return")
    repo_name: str | None = Field(default=None, description="Filter by repository name")
    module_name: str | None = Field(default=None, description="Filter by module name")


class CodeSearchRequest(SearchRequest):
    chunk_type: str | None = Field(
        default=None, description="Filter by chunk type (class, function, method, module_level)"
    )
    file_path: str | None = Field(default=None, description="Filter by file path substring")


class ViewSearchRequest(SearchRequest):
    view_type: str | None = Field(
        default=None, description="Filter by view type (form, tree, kanban, etc.)"
    )
    view_model: str | None = Field(default=None, description="Filter by Odoo model name")


class ManifestSearchRequest(SearchRequest):
    category: str | None = Field(default=None, description="Filter by module category")
    depends_on: str | None = Field(
        default=None, description="Filter modules that depend on a specific module"
    )


class SearchResult(BaseModel):
    score: float
    repo_name: str
    module_name: str
    file_path: str
    chunk_type: str
    chunk_name: str
    content: str
    start_line: int
    end_line: int
    # Optional fields
    class_name: str | None = None
    xml_id: str | None = None
    view_type: str | None = None
    view_model: str | None = None
    module_category: str | None = None
    module_depends: list[str] | None = None


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int


class DocGenerateRequest(BaseModel):
    module_name: str = Field(..., description="Name of the Odoo module to document")
    repo_name: str | None = Field(default=None, description="Repository containing the module")


class DocGenerateResponse(BaseModel):
    module_name: str
    documentation: str


class HealthResponse(BaseModel):
    status: str
    collections: dict[str, int]
