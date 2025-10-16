from __future__ import annotations

from typing import Iterable, List

from rich.console import Group
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import Footer, Header, RichLog

from .git_data import GitCommit, GitRepository


DEFAULT_CSS = """
Screen {
    layout: vertical;
}
#detail-panel {
    height: 1fr;
    border: solid $surface 10%;
    padding: 0 1;
}
"""


class _HistoryApp(App):
    """Textual application presenting git history for a single file."""

    CSS = DEFAULT_CSS
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("left", "prev_commit", "Previous", key_display="←"),
        Binding("right", "next_commit", "Next", key_display="→"),
        Binding("tab", "focus_cycle", "Cycle focus", show=False),
    ]

    def __init__(
        self, repo: GitRepository, commits: Iterable[GitCommit], file_path: str
    ) -> None:
        super().__init__()
        self.repo = repo
        self.commits: List[GitCommit] = list(commits)
        self.file_path = file_path
        self.detail_log: RichLog | None = None
        self._current_index = 0
        self.title = f"git history: {file_path}"
        self.sub_title = repo.path

    def compose(self) -> ComposeResult:
        self.detail_log = RichLog(
            id="commit-detail",
            highlight=True,
            wrap=False,
            auto_scroll=False,
        )
        yield Header(show_clock=False)
        yield Container(self.detail_log, id="detail-panel")
        yield Footer()

    def on_mount(self) -> None:
        assert self.detail_log is not None
        if not self.commits:
            self.detail_log.write(Text("No commits found.", style="italic"))
            return
        self._select_index(0)
        self.set_focus(self.detail_log)

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

    def _show_commit(self, commit: GitCommit, index: int) -> None:
        assert self.detail_log is not None
        total = len(self.commits)
        meta = Text()
        meta.append(f"commit {commit.oid}\n", style="bold")
        meta.append(f"Author: {commit.author_name} <{commit.author_email}>\n")
        meta.append(f"Date:   {commit.authored_at.strftime('%Y-%m-%d %H:%M:%S')}\n")
        meta.append(f"File:   {self.file_path}\n")
        meta.append(f"Show:   {index + 1}/{total} commits\n\n")

        message = Text()
        message.append("Message:\n", style="bold")
        if commit.title:
            message.append(f"{commit.title}\n", style="italic")
        if commit.body.strip():
            message.append(commit.body.rstrip() + "\n")
        message.append("\n")

        parent = commit.parent_oids[0] if commit.parent_oids else None
        diff = self.repo.get_file_diff(commit.oid, self.file_path, parent)
        diff_table = self._build_diff_table(diff.splitlines())
        self.detail_log.clear()
        self.detail_log.write(Group(meta, message, diff_table))
        self.detail_log.scroll_home()

    def _build_diff_table(self, lines: List[str]) -> Table:
        table = Table(
            show_header=True,
            header_style="bold",
            box=None,
            expand=True,
            pad_edge=False,
        )
        table.add_column("Removed", style="red", ratio=1)
        table.add_column("Context", ratio=1)
        table.add_column("Added", style="green", ratio=1)
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
                table.add_row(Text(line, style="red"), "", "")
            elif line.startswith("+"):
                table.add_row("", "", Text(line, style="green"))
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
        self._show_commit(commit, index)


class HistoryTUI:
    """Public interface mirroring the previous curses-based wrapper."""

    def __init__(
        self, repo: GitRepository, commits: Iterable[GitCommit], file_path: str
    ) -> None:
        self._app = _HistoryApp(repo, commits, file_path)

    def run(self) -> None:
        self._app.run()
