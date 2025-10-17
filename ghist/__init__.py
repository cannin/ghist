"""Terminal UI for navigating git history."""

from importlib import metadata

try:
    __version__ = metadata.version("ghist")
except metadata.PackageNotFoundError:
    __version__ = "0.0.0"

from .git_data import GitCommit, GitRepository, GitError  # noqa: E402
from .ui import HistoryTUI  # noqa: E402

__all__ = [
    "GitCommit",
    "GitRepository",
    "GitError",
    "HistoryTUI",
    "__version__",
]
