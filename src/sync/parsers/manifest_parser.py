"""Parse __manifest__.py files into a single structured chunk."""

from __future__ import annotations

import ast
import logging
from pathlib import Path

from repo_sync.models import ChunkType, CollectionName, ContentChunk

logger = logging.getLogger(__name__)


def parse_manifest(
    manifest_path: Path,
    repo_name: str,
    module_name: str,
) -> ContentChunk | None:
    """Parse an Odoo __manifest__.py and return a single chunk."""
    try:
        source = manifest_path.read_text(encoding="utf-8", errors="replace")
        manifest_dict = ast.literal_eval(source)
    except Exception:
        logger.warning("Failed to parse manifest: %s", manifest_path)
        return None

    if not isinstance(manifest_dict, dict):
        logger.warning("Manifest is not a dict: %s", manifest_path)
        return None

    # Build a natural-language summary for better embedding quality
    summary_parts = [f"Odoo module: {manifest_dict.get('name', module_name)}"]

    if desc := manifest_dict.get("summary") or manifest_dict.get("description"):
        summary_parts.append(f"Description: {desc}")
    if category := manifest_dict.get("category"):
        summary_parts.append(f"Category: {category}")
    if version := manifest_dict.get("version"):
        summary_parts.append(f"Version: {version}")

    depends = manifest_dict.get("depends", [])
    if depends:
        summary_parts.append(f"Depends on: {', '.join(depends)}")

    if data_files := manifest_dict.get("data"):
        summary_parts.append(f"Data files: {', '.join(data_files)}")
    if demo_files := manifest_dict.get("demo"):
        summary_parts.append(f"Demo files: {', '.join(demo_files)}")

    if manifest_dict.get("installable") is False:
        summary_parts.append("Status: NOT installable")
    if manifest_dict.get("application"):
        summary_parts.append("Type: Application")

    rel_path = f"{module_name}/__manifest__.py"
    content = "\n".join(summary_parts)
    lines = source.splitlines()

    return ContentChunk(
        repo_name=repo_name,
        module_name=module_name,
        file_path=rel_path,
        chunk_type=ChunkType.MANIFEST,
        chunk_name="manifest",
        start_line=1,
        end_line=len(lines),
        content=content,
        collection=CollectionName.MANIFESTS,
        module_category=manifest_dict.get("category"),
        module_depends=depends if isinstance(depends, list) else [],
    )
