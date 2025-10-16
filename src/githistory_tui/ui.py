from __future__ import annotations

from typing import Iterable, List

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, ListItem, ListView, Static, TextLog

from .git_data import GitCommit, GitRepository


DEFAULT_CSS = """
Screen {
    layout: vertical;
}
#body {
    height: 1fr;
}
#list-panel, #detail-panel {
    height: 1fr;
    border: solid $surface 10%;
}
#list-panel {
    width: 40%;
    min-width: 30;
    border-right: solid $surface 20%;
}
#detail-panel {
    width: 1fr;
}
.commit-item {
    padding: 1 1;
    border-bottom: solid rgba(128, 128, 128, 0.2);
}
.commit-title {
    text-style: bold;
}
.commit-meta, .commit-date {
    color: rgba(200, 200, 200, 0.8);
}
#commit-detail {
    padding: 0 1;
}
"""


class CommitListItem(ListItem):
    """ListView item encapsulating a commit record."""

    def __init__(self, commit: GitCommit) -> None:
        self.commit = commit
        summary = f"{commit.oid[:7]} {commit.title}"
        author = f"{commit.author_name} <{commit.author_email}>"
        timestamp = commit.authored_at.strftime("%Y-%m-%d %H:%M")
        super().__init__(
            Vertical(
                Static(summary, classes="commit-title"),
                Static(author, classes="commit-meta"),
                Static(timestamp, classes="commit-date"),
            ),
            classes="commit-item",
        )


class _HistoryApp(App):
    """Textual application presenting git history."""

    CSS = DEFAULT_CSS
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("left", "focus_list", "Focus list"),
        Binding("right", "focus_detail", "Focus detail"),
    ]

    def __init__(self, repo: GitRepository, commits: Iterable[GitCommit]) -> None:
        super().__init__()
        self.repo = repo
        self.commits: List[GitCommit] = list(commits)
        self.list_view: ListView | None = None
        self.detail_log: TextLog | None = None

    def compose(self) -> ComposeResult:
        self.list_view = ListView(id="commit-list")
        self.detail_log = TextLog(
            id="commit-detail",
            highlight=True,
            wrap=False,
            auto_scroll=False,
        )
        yield Header(show_clock=False)
        yield Horizontal(
            Container(self.list_view, id="list-panel"),
            Container(self.detail_log, id="detail-panel"),
            id="body",
        )
        yield Footer()

    def on_mount(self) -> None:
        assert self.list_view is not None
        assert self.detail_log is not None
        if not self.commits:
            self.detail_log.write("No commits found.")
            return
        for commit in self.commits:
            self.list_view.append(CommitListItem(commit))
        self.list_view.index = 0
        self._show_commit(self.commits[0])
        self.set_focus(self.list_view)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        item = event.item
        if isinstance(item, CommitListItem):
            self._show_commit(item.commit)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, CommitListItem):
            self._show_commit(item.commit)

    def action_focus_list(self) -> None:
        if self.list_view is not None:
            self.set_focus(self.list_view)

    def action_focus_detail(self) -> None:
        if self.detail_log is not None:
            self.set_focus(self.detail_log)

    def _show_commit(self, commit: GitCommit) -> None:
        assert self.detail_log is not None
        text = Text()
        text.append(f"commit {commit.oid}\n", style="bold")
        text.append(f"Author: {commit.author_name} <{commit.author_email}>\n")
        text.append(f"Date:   {commit.authored_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        if commit.title:
            text.append(f"{commit.title}\n\n", style="italic")
        if commit.body.strip():
            for line in commit.body.splitlines():
                text.append(line + "\n")
            text.append("\n")
        parent = commit.parent_oids[0] if commit.parent_oids else None
        diff = self.repo.get_diff(commit.oid, parent)
        for line in diff.splitlines():
            style = ""
            if line.startswith("diff --git") or line.startswith("@@"):
                style = "bold"
            elif line.startswith("+"):
                style = "bold green"
            elif line.startswith("-"):
                style = "bold red"
            text.append(line + "\n", style=style or None)
        self.detail_log.clear()
        self.detail_log.write(text)


class HistoryTUI:
    """Public interface mirroring the previous curses-based wrapper."""

    def __init__(self, repo: GitRepository, commits: Iterable[GitCommit]) -> None:
        self._app = _HistoryApp(repo, commits)

    def run(self) -> None:
        self._app.run()
