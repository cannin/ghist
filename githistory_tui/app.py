from __future__ import annotations

import argparse
import os
import sys
from typing import Sequence

from .git_data import GitError, GitRepository
from .ui import HistoryTUI


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="githistory-tui",
        description="View the history of a single file using a terminal UI.",
    )
    parser.add_argument(
        "file",
        help="Absolute or relative path to a tracked file (e.g. /path/to/repo/README.md).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=256,
        help="Number of commits to load (default: 256)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    file_path = os.path.abspath(args.file)
    if not os.path.exists(file_path):
        print(f"error: file does not exist: {file_path}", file=sys.stderr)
        return 1
    if os.path.isdir(file_path):
        print(f"error: expected a file, not a directory: {file_path}", file=sys.stderr)
        return 1
    repo_root = _find_git_root(os.path.dirname(file_path))
    if repo_root is None:
        print("error: could not locate a .git directory in parent folders.", file=sys.stderr)
        return 1
    rel_path = os.path.relpath(file_path, repo_root)
    # Prevent traversing outside the repository via symlinks/.. components.
    try:
        common = os.path.commonpath([repo_root, file_path])
    except ValueError:
        common = ""
    if common != repo_root:
        print(
            f"error: file {file_path} is not inside repository {repo_root}",
            file=sys.stderr,
        )
        return 1
    git_rel_path = rel_path.replace(os.sep, "/")
    limit = max(1, args.limit)
    try:
        repo = GitRepository(repo_root)
        commits = repo.list_file_commits(git_rel_path, limit=limit)
    except GitError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    if not commits:
        print(
            f"No commits found for {git_rel_path}. Is the file tracked?",
            file=sys.stderr,
        )
        return 1
    try:
        tui = HistoryTUI(repo, commits, git_rel_path)
        tui.run()
    except KeyboardInterrupt:
        return 130
    return 0


def _find_git_root(start_dir: str) -> str | None:
    path = os.path.abspath(start_dir)
    while True:
        if os.path.isdir(os.path.join(path, ".git")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


if __name__ == "__main__":
    raise SystemExit(main())
