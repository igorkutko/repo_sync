"""Line-based chunking for JS, CSS, and other file types."""

from __future__ import annotations

import logging
from pathlib import Path

from common.models import ChunkType, CollectionName, ContentChunk

logger = logging.getLogger(__name__)


def parse_generic_file(
    file_path: Path,
    repo_name: str,
    module_name: str,
    rel_path: str,
    chunk_lines: int = 200,
    overlap_lines: int = 20,
) -> list[ContentChunk]:
    """Split a file into overlapping line-based chunks."""
    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        logger.warning("Cannot read file: %s", file_path)
        return []

    lines = source.splitlines()
    if not lines:
        return []

    chunks: list[ContentChunk] = []
    start = 0

    while start < len(lines):
        end = min(start + chunk_lines, len(lines))
        chunk_content = "\n".join(lines[start:end])

        chunk_index = len(chunks)
        chunks.append(
            ContentChunk(
                repo_name=repo_name,
                module_name=module_name,
                file_path=rel_path,
                chunk_type=ChunkType.GENERIC,
                chunk_name=f"{Path(rel_path).stem}_chunk_{chunk_index}",
                start_line=start + 1,
                end_line=end,
                content=chunk_content,
                collection=CollectionName.CODE,
            )
        )

        if end >= len(lines):
            break
        start = end - overlap_lines

    return chunks
