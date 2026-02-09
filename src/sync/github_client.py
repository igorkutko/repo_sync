"""GitHub API client for listing org repos and cloning/pulling."""

from __future__ import annotations

import logging
from pathlib import Path

from git import Repo as GitRepo
from github import Github

from common.config import Settings

logger = logging.getLogger(__name__)


class GitHubClient:
    def __init__(self, settings: Settings) -> None:
        self._token = settings.github_token
        self._gh = Github(self._token)
        self._org_name = settings.github_org_name
        self._repos_dir = settings.repos_dir

    def list_repos(self) -> list[str]:
        """Return list of repo full names in the org."""
        org = self._gh.get_organization(self._org_name)
        repos = []
        for repo in org.get_repos(type="all"):
            if not repo.archived:
                repos.append(repo.full_name)
        logger.info("Found %d repos in org %s", len(repos), self._org_name)
        return repos

    def clone_or_pull(self, repo_full_name: str) -> Path:
        """Clone a repo if not present, otherwise pull latest changes.

        Returns the local path to the repo.
        """
        repo_short = repo_full_name.split("/")[-1]
        local_path = self._repos_dir / repo_short

        if (local_path / ".git").is_dir():
            logger.info("Pulling latest for %s", repo_full_name)
            git_repo = GitRepo(str(local_path))
            origin = git_repo.remotes.origin
            origin.pull()
        else:
            logger.info("Cloning %s", repo_full_name)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            clone_url = f"https://x-access-token:{self._token}@github.com/{repo_full_name}.git"
            GitRepo.clone_from(clone_url, str(local_path))

        return local_path

    def get_head_sha(self, repo_path: Path) -> str:
        """Get the HEAD commit SHA of a local repo."""
        git_repo = GitRepo(str(repo_path))
        return git_repo.head.commit.hexsha

    def get_changed_files(self, repo_path: Path, since_sha: str) -> list[str]:
        """Get list of changed files between since_sha and HEAD."""
        git_repo = GitRepo(str(repo_path))
        head_sha = git_repo.head.commit.hexsha

        if since_sha == head_sha:
            return []

        try:
            diff = git_repo.git.diff("--name-only", since_sha, head_sha)
            return [f for f in diff.splitlines() if f.strip()]
        except Exception:
            logger.warning(
                "Cannot diff %s..%s in %s, treating as full resync",
                since_sha,
                head_sha,
                repo_path,
            )
            return ["__full_resync__"]

    def close(self) -> None:
        self._gh.close()
