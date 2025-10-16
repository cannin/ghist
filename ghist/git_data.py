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

    def list_file_commits(
        self, file_path: str, limit: int = 256, follow: bool = True
    ) -> List[GitCommit]:
        """Return commits affecting the given file ordered by recency."""
        pretty = "%H%x1f%P%x1f%an%x1f%ae%x1f%ad%x1f%s%x1f%b%x1e"
        args = [
            "log",
            f"-n{limit}",
            "--date=iso8601-strict",
            f"--pretty=format:{pretty}",
        ]
        if follow:
            args.append("--follow")
        args.extend(["--", file_path])
        result = self._run(*args)
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
            oid = oid.strip()
            parent_list = [p.strip() for p in parents.split(" ") if p.strip()]
            commits.append(
                GitCommit(
                    oid=oid,
                    parent_oids=parent_list,
                    author_name=author_name.strip(),
                    author_email=author_email.strip(),
                    authored_at=datetime.fromisoformat(authored_at.strip()),
                    title=title.strip(),
                    body=body.rstrip(),
                )
            )
        return commits

    @lru_cache(maxsize=128)
    def get_file_diff(
        self, oid: str, file_path: str, parent_oid: Optional[str] = None
    ) -> str:
        """Return the diff for the file between this commit and its parent."""
        args = ["show", oid, "--patch", "--stat", "--", file_path]
        if parent_oid:
            args = ["diff", f"{parent_oid}", oid, "--", file_path]
        result = self._run(*args)
        return result.stdout

    @lru_cache(maxsize=256)
    def get_file_contents(self, oid: str, file_path: str) -> str:
        """Return the file contents at a specific commit."""
        result = self._run("show", f"{oid}:{file_path}")
        return result.stdout


def iter_walker(commits: Iterable[GitCommit]) -> Iterable[GitCommit]:
    """Yield commits preserving input order; helper for typing clarity."""
    return commits


class GitError(RuntimeError):
    """Raised when git commands fail."""
