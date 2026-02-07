"""AST-based Python file parser for Odoo modules."""

from __future__ import annotations

import ast
import logging
from pathlib import Path

import tiktoken

from models import ChunkType, CollectionName, ContentChunk

logger = logging.getLogger(__name__)

_encoder = tiktoken.get_encoding("cl100k_base")

MAX_CLASS_TOKENS = 6000


def _count_tokens(text: str) -> int:
    return len(_encoder.encode(text))


def _get_source_segment(lines: list[str], node: ast.AST) -> str:
    """Extract source lines for an AST node."""
    start = node.lineno - 1
    end = node.end_lineno if node.end_lineno else start + 1
    return "\n".join(lines[start:end])


def parse_python_file(
    file_path: Path,
    repo_name: str,
    module_name: str,
    rel_path: str,
) -> list[ContentChunk]:
    """Parse a Python file into chunks using AST."""
    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        logger.warning("Cannot read file: %s", file_path)
        return []

    try:
        tree = ast.parse(source)
    except SyntaxError:
        logger.warning("Syntax error in %s, falling back to single chunk", file_path)
        lines = source.splitlines()
        if not lines:
            return []
        return [
            ContentChunk(
                repo_name=repo_name,
                module_name=module_name,
                file_path=rel_path,
                chunk_type=ChunkType.MODULE_LEVEL,
                chunk_name=Path(rel_path).stem,
                start_line=1,
                end_line=len(lines),
                content=source,
                collection=CollectionName.CODE,
            )
        ]

    lines = source.splitlines()
    chunks: list[ContentChunk] = []

    # Collect top-level nodes
    module_level_parts: list[tuple[int, int, str]] = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            chunks.extend(
                _parse_class(node, lines, repo_name, module_name, rel_path)
            )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            segment = _get_source_segment(lines, node)
            chunks.append(
                ContentChunk(
                    repo_name=repo_name,
                    module_name=module_name,
                    file_path=rel_path,
                    chunk_type=ChunkType.FUNCTION,
                    chunk_name=node.name,
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    content=segment,
                    collection=CollectionName.CODE,
                )
            )
        else:
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                segment = _get_source_segment(lines, node)
                module_level_parts.append(
                    (node.lineno, node.end_lineno or node.lineno, segment)
                )

    # Combine module-level statements into one chunk
    if module_level_parts:
        combined = "\n".join(part[2] for part in module_level_parts)
        if combined.strip():
            chunks.append(
                ContentChunk(
                    repo_name=repo_name,
                    module_name=module_name,
                    file_path=rel_path,
                    chunk_type=ChunkType.MODULE_LEVEL,
                    chunk_name=f"{Path(rel_path).stem}_module_level",
                    start_line=module_level_parts[0][0],
                    end_line=module_level_parts[-1][1],
                    content=combined,
                    collection=CollectionName.CODE,
                )
            )

    return chunks


def _parse_class(
    node: ast.ClassDef,
    lines: list[str],
    repo_name: str,
    module_name: str,
    rel_path: str,
) -> list[ContentChunk]:
    """Parse a class, splitting into methods if too large."""
    class_source = _get_source_segment(lines, node)
    tokens = _count_tokens(class_source)

    if tokens <= MAX_CLASS_TOKENS:
        return [
            ContentChunk(
                repo_name=repo_name,
                module_name=module_name,
                file_path=rel_path,
                chunk_type=ChunkType.CLASS,
                chunk_name=node.name,
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
                content=class_source,
                collection=CollectionName.CODE,
                class_name=node.name,
            )
        ]

    # Class is too large — split into individual methods
    chunks: list[ContentChunk] = []
    method_nodes: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    class_level_parts: list[tuple[int, int, str]] = []

    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            method_nodes.append(child)
        elif hasattr(child, "lineno") and hasattr(child, "end_lineno"):
            segment = _get_source_segment(lines, child)
            class_level_parts.append(
                (child.lineno, child.end_lineno or child.lineno, segment)
            )

    # Class-level attributes/assignments as one chunk
    if class_level_parts:
        combined = "\n".join(p[2] for p in class_level_parts)
        if combined.strip():
            chunks.append(
                ContentChunk(
                    repo_name=repo_name,
                    module_name=module_name,
                    file_path=rel_path,
                    chunk_type=ChunkType.CLASS,
                    chunk_name=f"{node.name}_attrs",
                    start_line=class_level_parts[0][0],
                    end_line=class_level_parts[-1][1],
                    content=combined,
                    collection=CollectionName.CODE,
                    class_name=node.name,
                )
            )

    for method in method_nodes:
        segment = _get_source_segment(lines, method)
        chunks.append(
            ContentChunk(
                repo_name=repo_name,
                module_name=module_name,
                file_path=rel_path,
                chunk_type=ChunkType.METHOD,
                chunk_name=f"{node.name}.{method.name}",
                start_line=method.lineno,
                end_line=method.end_lineno or method.lineno,
                content=segment,
                collection=CollectionName.CODE,
                class_name=node.name,
            )
        )

    return chunks
