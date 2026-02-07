"""Discover Odoo modules within cloned repositories."""

from __future__ import annotations

import ast
import logging
from pathlib import Path

from models import OdooModule

logger = logging.getLogger(__name__)


def discover_modules(repo_path: Path, repo_name: str) -> list[OdooModule]:
    """Walk a repo directory and find all Odoo modules (dirs with __manifest__.py)."""
    modules: list[OdooModule] = []

    for manifest_path in repo_path.rglob("__manifest__.py"):
        module_dir = manifest_path.parent
        module_name = module_dir.name

        # Skip hidden directories and common non-module paths
        parts = manifest_path.relative_to(repo_path).parts
        if any(p.startswith(".") for p in parts):
            continue

        # Parse manifest to extract metadata
        manifest_dict = _safe_parse_manifest(manifest_path)

        modules.append(
            OdooModule(
                repo_name=repo_name,
                module_name=module_name,
                module_path=str(module_dir),
                manifest=manifest_dict,
            )
        )

    logger.info("Found %d Odoo modules in %s", len(modules), repo_name)
    return modules


def filter_changed_modules(
    modules: list[OdooModule],
    changed_files: list[str],
    repo_path: Path,
) -> list[OdooModule]:
    """Filter modules to only those containing changed files."""
    if "__full_resync__" in changed_files:
        return modules

    changed_set = set(changed_files)
    result: list[OdooModule] = []

    for module in modules:
        module_rel = str(Path(module.module_path).relative_to(repo_path))
        # Check if any changed file is within this module's directory
        for changed in changed_set:
            if changed.startswith(module_rel.replace("\\", "/")):
                result.append(module)
                break

    return result


def _safe_parse_manifest(manifest_path: Path) -> dict:
    """Safely parse a __manifest__.py file."""
    try:
        source = manifest_path.read_text(encoding="utf-8", errors="replace")
        result = ast.literal_eval(source)
        return result if isinstance(result, dict) else {}
    except Exception:
        logger.warning("Failed to parse manifest: %s", manifest_path)
        return {}
