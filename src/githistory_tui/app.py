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
        "--repo",
        default=".",
        help="Path to the git repository (default: current directory)",
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
