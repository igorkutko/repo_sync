"""Data models and enums for the sync pipeline."""

from __future__ import annotations

import uuid
from enum import StrEnum

from pydantic import BaseModel, Field


class ChunkType(StrEnum):
    CLASS = "class"
    FUNCTION = "function"
    MODULE_LEVEL = "module_level"
    METHOD = "method"
    MANIFEST = "manifest"
    XML_RECORD = "xml_record"
    XML_TEMPLATE = "xml_template"
    XML_MENUITEM = "xml_menuitem"
    GENERIC = "generic"


class CollectionName(StrEnum):
    CODE = "odoo_code"
    MANIFESTS = "odoo_manifests"
    VIEWS = "odoo_views"


class ContentChunk(BaseModel):
    """A single chunk of content ready for embedding."""

    repo_name: str
    module_name: str
    file_path: str
    chunk_type: ChunkType
    chunk_name: str
    start_line: int
    end_line: int
    content: str
    collection: CollectionName

    # Optional metadata (varies by chunk type)
    class_name: str | None = None
    xml_id: str | None = None
    view_type: str | None = None
    view_model: str | None = None
    module_category: str | None = None
    module_depends: list[str] = Field(default_factory=list)

    @property
    def point_id(self) -> str:
        """Deterministic UUID5 for idempotent upserts."""
        key = f"{self.repo_name}:{self.module_name}:{self.file_path}:{self.chunk_name}:{self.start_line}"
        return str(uuid.uuid5(uuid.NAMESPACE_URL, key))

    @property
    def context_prefix(self) -> str:
        """Human-readable context prefix prepended to content for embedding."""
        parts = [f"Module: {self.module_name}", f"File: {self.file_path}"]
        if self.class_name:
            parts.append(f"Class: {self.class_name}")
        return " | ".join(parts)

    @property
    def text_for_embedding(self) -> str:
        return f"{self.context_prefix}\n\n{self.content}"

    def payload(self) -> dict:
        """Metadata payload for Qdrant point."""
        data: dict = {
            "repo_name": self.repo_name,
            "module_name": self.module_name,
            "file_path": self.file_path,
            "chunk_type": self.chunk_type.value,
            "chunk_name": self.chunk_name,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content": self.content,
        }
        if self.class_name:
            data["class_name"] = self.class_name
        if self.xml_id:
            data["xml_id"] = self.xml_id
        if self.view_type:
            data["view_type"] = self.view_type
        if self.view_model:
            data["view_model"] = self.view_model
        if self.module_category:
            data["module_category"] = self.module_category
        if self.module_depends:
            data["module_depends"] = self.module_depends
        return data


class OdooModule(BaseModel):
    """Represents a discovered Odoo module within a repo."""

    repo_name: str
    module_name: str
    module_path: str  # absolute path on disk
    manifest: dict = Field(default_factory=dict)
