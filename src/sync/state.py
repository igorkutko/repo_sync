"""Incremental sync state tracking via JSON file."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class SyncState:
    """Tracks last-synced commit SHA per repo for incremental sync."""

    def __init__(self, state_path: Path) -> None:
        self._path = state_path
        self._state: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._state = json.loads(self._path.read_text(encoding="utf-8"))
                logger.info("Loaded sync state with %d repos", len(self._state))
            except Exception:
                logger.warning("Failed to load sync state, starting fresh")
                self._state = {}

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._state, indent=2),
            encoding="utf-8",
        )

    def get_sha(self, repo_name: str) -> str | None:
        """Get last synced commit SHA for a repo."""
        return self._state.get(repo_name)

    def set_sha(self, repo_name: str, sha: str) -> None:
        """Update the synced commit SHA for a repo."""
        self._state[repo_name] = sha

    def has_changed(self, repo_name: str, current_sha: str) -> bool:
        """Check if a repo has changed since last sync."""
        stored = self.get_sha(repo_name)
        return stored is None or stored != current_sha
