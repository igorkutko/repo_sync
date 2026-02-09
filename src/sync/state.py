"""Incremental sync state tracking via PostgreSQL."""

from __future__ import annotations

import logging

import psycopg2
from common.config import Settings

logger = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS sync_state (
    repo_name   VARCHAR(255) PRIMARY KEY,
    commit_sha  VARCHAR(40)  NOT NULL,
    updated_at  TIMESTAMP    NOT NULL DEFAULT NOW()
);
"""

_SELECT_SHA = "SELECT commit_sha FROM sync_state WHERE repo_name = %s"

_UPSERT_SHA = """
INSERT INTO sync_state (repo_name, commit_sha, updated_at)
VALUES (%s, %s, NOW())
ON CONFLICT (repo_name)
DO UPDATE SET commit_sha = EXCLUDED.commit_sha, updated_at = NOW();
"""


class SyncState:
    """Tracks last-synced commit SHA per repo for incremental sync."""

    def __init__(self, settings: Settings) -> None:
        self._conn = psycopg2.connect(settings.database_url)
        self._conn.autocommit = False
        self._ensure_table()
        logger.info("Connected to sync state database")

    def _ensure_table(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute(_CREATE_TABLE)
        self._conn.commit()

    def get_sha(self, repo_name: str) -> str | None:
        """Get last synced commit SHA for a repo."""
        with self._conn.cursor() as cur:
            cur.execute(_SELECT_SHA, (repo_name,))
            row = cur.fetchone()
        return row[0] if row else None

    def set_sha(self, repo_name: str, sha: str) -> None:
        """Update the synced commit SHA for a repo."""
        with self._conn.cursor() as cur:
            cur.execute(_UPSERT_SHA, (repo_name, sha))

    def has_changed(self, repo_name: str, current_sha: str) -> bool:
        """Check if a repo has changed since last sync."""
        stored = self.get_sha(repo_name)
        return stored is None or stored != current_sha

    def save(self) -> None:
        """Commit the current transaction."""
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
