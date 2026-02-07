"""CLI entry point for the repo-sync command."""

from __future__ import annotations

import logging
import sys

from dotenv import load_dotenv

from repo_sync.config import Settings
from repo_sync.sync.pipeline import run_sync


def main() -> None:
    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    settings = Settings()  # type: ignore[call-arg]
    stats = run_sync(settings)

    print("\n=== Sync Summary ===")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
