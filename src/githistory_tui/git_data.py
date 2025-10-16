from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Iterable, List, Optional


@dataclass
class GitCommit:
    """Container for the metadata needed by the TUI."""

    oid: str
    parent_oids: List[str]
    author_name: str
    author_email: str
    authored_at: datetime
    title: str
    body: str


class GitRepository:
    """Thin wrapper on top of cli git interactions."""

    def __init__(self, path: str) -> None:
        self._path = path

    @property
    def path(self) -> str:
        return self._path

    def _run(self, *args: str, text: bool = True) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                ["git", *args],
                cwd=self._path,
                text=text,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise GitError("git executable not found") from exc
        except subprocess.CalledProcessError as exc:
            raise GitError(exc.stderr.strip() or exc.stdout.strip()) from exc

    def list_commits(self, limit: int = 256) -> List[GitCommit]:
        """Return commits ordered by recency."""
        pretty = "%H%x1f%P%x1f%an%x1f%ae%x1f%ad%x1f%s%x1f%b%x1e"
        result = self._run(
            "log",
            f"-n{limit}",
            "--date=iso8601-strict",
            f"--pretty=format:{pretty}",
        )
        commits: List[GitCommit] = []
        for entry in filter(None, result.stdout.split("\x1e")):
            (
                oid,
                parents,
                author_name,
                author_email,
                authored_at,
                title,
                body,
            ) = entry.split("\x1f")
            commits.append(
                GitCommit(
                    oid=oid,
                    parent_oids=[p for p in parents.split(" ") if p],
                    author_name=author_name,
                    author_email=author_email,
                    authored_at=datetime.fromisoformat(authored_at),
                    title=title,
                    body=body.rstrip(),
                )
            )
        return commits

    @lru_cache(maxsize=128)
    def get_diff(self, oid: str, parent_oid: Optional[str] = None) -> str:
        """Return a textual diff for the commit compared to its first parent."""
        args = ["show", oid, "--stat", "--patch"]
        if parent_oid:
            args = ["diff", f"{parent_oid}", oid]
        result = self._run(*args)
        return result.stdout


def iter_walker(commits: Iterable[GitCommit]) -> Iterable[GitCommit]:
    """Yield commits preserving input order; helper for typing clarity."""
    return commits


class GitError(RuntimeError):
    """Raised when git commands fail."""
