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
        description="Navigate git history using an interactive terminal UI.",
    )
    parser.add_argument(
        "repo",
        nargs="?",
        default=".",
        help="Path to the git repository root (must contain .git). Defaults to current directory.",
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
    path = os.path.abspath(args.repo)
    if os.path.basename(path) == ".git":
        path = os.path.dirname(path)
    git_dir = os.path.join(path, ".git")
    if not os.path.isdir(path):
        print(f"error: repository path does not exist: {path}", file=sys.stderr)
        return 1
    if not os.path.isdir(git_dir):
        print(f"error: expected '.git' directory inside {path}", file=sys.stderr)
        return 1
    limit = max(1, args.limit)
    try:
        repo = GitRepository(path)
        commits = repo.list_commits(limit=limit)
    except GitError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    if not commits:
        print("No commits found. Is this a git repository?", file=sys.stderr)
        return 1
    try:
        tui = HistoryTUI(repo, commits)
        tui.run()
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
