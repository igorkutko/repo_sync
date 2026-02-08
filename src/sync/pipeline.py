"""Orchestrates the full sync workflow."""

from __future__ import annotations

import logging
from pathlib import Path

from config import Settings
from models import ContentChunk, OdooModule
from sync.embeddings import EmbeddingClient
from sync.github_client import GitHubClient
from sync.odoo_discovery import discover_modules, filter_changed_modules
from sync.parsers import (
    parse_generic_file,
    parse_manifest,
    parse_python_file,
    parse_xml_file,
)
from sync.qdrant_loader import QdrantLoader
from sync.state import SyncState

logger = logging.getLogger(__name__)

PYTHON_EXTENSIONS = {".py"}
XML_EXTENSIONS = {".xml", ".html"}
SKIP_FILES = {"__manifest__.py", "__init__.py"}
GENERIC_EXTENSIONS = {".js", ".css", ".scss", ".less", ".txt", ".csv", ".md", ".rst", ".po"}


def parse_module(module: OdooModule, settings: Settings) -> list[ContentChunk]:
    """Parse all files in an Odoo module into chunks."""
    module_path = Path(module.module_path)
    chunks: list[ContentChunk] = []

    # Parse manifest
    manifest_path = module_path / "__manifest__.py"
    if manifest_path.exists():
        chunk = parse_manifest(manifest_path, module.repo_name, module.module_name)
        if chunk:
            chunks.append(chunk)

    # Walk all files in the module
    for file_path in module_path.rglob("*"):
        if not file_path.is_file():
            continue

        # Build relative path from module root
        rel_path = str(file_path.relative_to(module_path.parent)).replace("\\", "/")
        suffix = file_path.suffix.lower()

        if file_path.name in SKIP_FILES:
            continue

        if suffix in PYTHON_EXTENSIONS:
            chunks.extend(
                parse_python_file(
                    file_path, module.repo_name, module.module_name, rel_path
                )
            )
        elif suffix in XML_EXTENSIONS:
            chunks.extend(
                parse_xml_file(
                    file_path, module.repo_name, module.module_name, rel_path
                )
            )
        elif suffix in GENERIC_EXTENSIONS:
            chunks.extend(
                parse_generic_file(
                    file_path,
                    module.repo_name,
                    module.module_name,
                    rel_path,
                    chunk_lines=settings.generic_chunk_lines,
                    overlap_lines=settings.generic_chunk_overlap,
                )
            )

    return chunks


def run_sync(settings: Settings) -> dict:
    """Run the full sync pipeline.

    Returns a summary dict with stats.
    """
    github = GitHubClient(settings)
    embedder = EmbeddingClient(settings)
    loader = QdrantLoader(settings)
    state = SyncState(settings)

    # Ensure Qdrant collections exist
    loader.ensure_collections()

    stats = {
        "repos_found": 0,
        "repos_synced": 0,
        "repos_skipped": 0,
        "modules_processed": 0,
        "chunks_embedded": 0,
    }

    try:
        repo_names = github.list_repos()
        stats["repos_found"] = len(repo_names)

        for repo_full_name in repo_names:
            repo_short = repo_full_name.split("/")[-1]

            try:
                # Clone or pull
                repo_path = github.clone_or_pull(repo_full_name)
                current_sha = github.get_head_sha(repo_path)

                # Check if repo has changed
                if not state.has_changed(repo_short, current_sha):
                    logger.info("Skipping %s (unchanged)", repo_short)
                    stats["repos_skipped"] += 1
                    continue

                # Discover modules
                modules = discover_modules(repo_path, repo_short)

                # Determine which modules need re-indexing
                previous_sha = state.get_sha(repo_short)
                if previous_sha:
                    changed_files = github.get_changed_files(repo_path, previous_sha)
                    modules = filter_changed_modules(modules, changed_files, repo_path)

                # Process each module
                for module in modules:
                    logger.info(
                        "Processing module %s/%s",
                        module.repo_name,
                        module.module_name,
                    )

                    # Delete old points for this module
                    loader.delete_module_points(module.repo_name, module.module_name)

                    # Parse into chunks
                    chunks = parse_module(module, settings)
                    if not chunks:
                        continue

                    # Embed all chunks
                    embeddings = embedder.embed_chunks(chunks)

                    # Upsert into Qdrant
                    loader.upsert_chunks(chunks, embeddings)

                    stats["modules_processed"] += 1
                    stats["chunks_embedded"] += len(chunks)

                # Update sync state
                state.set_sha(repo_short, current_sha)
                stats["repos_synced"] += 1

            except Exception:
                logger.exception("Error processing repo %s", repo_full_name)

            break

        state.save()

    finally:
        state.close()
        github.close()

    logger.info("Sync complete: %s", stats)
    return stats
