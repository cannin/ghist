from __future__ import annotations

from typing import Iterable, List

from rich.console import Group
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, ListItem, ListView, ScrollView, Static

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
    height: 1fr;
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
        Binding("left", "prev_commit", "Previous", key_display="←"),
        Binding("right", "next_commit", "Next", key_display="→"),
        Binding("tab", "focus_cycle", "Cycle focus", show=False),
    ]

    def __init__(self, repo: GitRepository, commits: Iterable[GitCommit]) -> None:
        super().__init__()
        self.repo = repo
        self.commits: List[GitCommit] = list(commits)
        self.list_view: ListView | None = None
        self.detail_view: ScrollView | None = None
        self._current_index = 0

    def compose(self) -> ComposeResult:
        self.list_view = ListView(id="commit-list")
        self.detail_view = ScrollView(id="commit-detail", auto_width=True)
        yield Header(show_clock=False)
        yield Horizontal(
            Container(self.list_view, id="list-panel"),
            Container(self.detail_view, id="detail-panel"),
            id="body",
        )
        yield Footer()

    def on_mount(self) -> None:
        assert self.list_view is not None
        assert self.detail_view is not None
        if not self.commits:
            self.detail_view.update(Text("No commits found.", style="italic"))
            return
        for commit in self.commits:
            self.list_view.append(CommitListItem(commit))
        self._select_index(0)
        self.set_focus(self.list_view)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        item = event.item
        if isinstance(item, CommitListItem):
            index = self.list_view.index if self.list_view else 0
            self._select_index(index)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, CommitListItem):
            index = self.list_view.index if self.list_view else 0
            self._select_index(index)

    def action_prev_commit(self) -> None:
        if not self.commits:
            return
        new_index = max(0, self._current_index - 1)
        self._select_index(new_index)

    def action_next_commit(self) -> None:
        if not self.commits:
            return
        new_index = min(len(self.commits) - 1, self._current_index + 1)
        self._select_index(new_index)

    def _show_commit(self, commit: GitCommit) -> None:
        assert self.detail_view is not None
        meta = Text()
        meta.append(f"commit {commit.oid}\n", style="bold")
        meta.append(f"Author: {commit.author_name} <{commit.author_email}>\n")
        meta.append(f"Date:   {commit.authored_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        if commit.title:
            meta.append(f"{commit.title}\n\n", style="italic")
        if commit.body.strip():
            meta.append(commit.body.rstrip() + "\n\n")
        parent = commit.parent_oids[0] if commit.parent_oids else None
        diff = self.repo.get_diff(commit.oid, parent)
        diff_table = self._build_diff_table(diff.splitlines())
        self.detail_view.update(Group(meta, diff_table))
        self.detail_view.scroll_home()

    def _build_diff_table(self, lines: List[str]) -> Table:
        table = Table(
            show_header=True,
            header_style="bold",
            box=None,
            expand=True,
            pad_edge=False,
        )
        table.add_column("Removed", style="red", no_wrap=True)
        table.add_column("Current", no_wrap=True)
        table.add_column("Added", style="green", no_wrap=True)
        for raw in lines:
            line = raw.rstrip("\n")
            if line.startswith("diff --git"):
                table.add_row("", Text(line, style="cyan"), "")
            elif line.startswith("@@"):
                table.add_row("", Text(line, style="yellow"), "")
            elif line.startswith("---"):
                table.add_row(Text(line, style="red"), "", "")
            elif line.startswith("+++"):
                table.add_row("", Text(line, style="green"), "")
            elif line.startswith("-"):
                content = line[1:]
                table.add_row(Text(content, style="red"), "", "")
            elif line.startswith("+"):
                content = line[1:]
                center = Text(content, style="green")
                right = Text(content, style="green dim")
                table.add_row("", center, right)
            elif line.startswith("index"):
                table.add_row(Text(line, style="magenta"), "", "")
            else:
                content = line[1:] if line.startswith(" ") else line
                table.add_row("", Text(content), "")
        return table

    def _select_index(self, index: int) -> None:
        if not self.commits:
            return
        index = max(0, min(len(self.commits) - 1, index))
        commit = self.commits[index]
        self._current_index = index
        if self.list_view is not None:
            if self.list_view.index != index:
                self.list_view.index = index
            self._scroll_list_to_index(index)
        self._show_commit(commit)

    def _scroll_list_to_index(self, index: int) -> None:
        if self.list_view is None:
            return
        try:
            self.list_view.scroll_to_index(index)
        except AttributeError:
            pass


class HistoryTUI:
    """Public interface mirroring the previous curses-based wrapper."""

    def __init__(self, repo: GitRepository, commits: Iterable[GitCommit]) -> None:
        self._app = _HistoryApp(repo, commits)

    def run(self) -> None:
        self._app.run()
