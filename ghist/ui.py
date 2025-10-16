from __future__ import annotations

import os
from typing import Iterable, List

from rich.console import Group
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, RichLog, Static

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
FilePromptScreen {
    align: center middle;
}
FilePromptScreen #prompt-modal {
    width: 60%;
    max-width: 80;
    height: 50%;
    padding: 1 2;
    border: solid $accent 30%;
    background: $surface;
}
FilePromptScreen .prompt-body {
    layout: vertical;
}
FilePromptScreen .prompt-buttons {
    layout: horizontal;
    align-horizontal: right;
}
"""


class FilePromptScreen(ModalScreen[str | None]):
    """Modal dialog allowing the user to pick a different file."""

    def __init__(self, initial_path: str) -> None:
        super().__init__()
        self._initial_path = initial_path

    def compose(self) -> ComposeResult:
        with Container(id="prompt-modal"):
            with Vertical(classes="prompt-body") as body:
                body.styles.gap = 1
                yield Static(
                    "Enter a file path (absolute or relative):", classes="prompt-label"
                )
                file_input = Input(
                    value=self._initial_path,
                    placeholder="path/to/file",
                    id="file-input",
                )
                file_input.styles.margin_top = 0  # gap handles spacing
                yield file_input
                with Horizontal(classes="prompt-buttons") as buttons:
                    buttons.styles.align_horizontal = "center"
                    buttons.styles.gap = 1
                    buttons.styles.margin_top = 1
                    yield Button("Cancel", id="cancel")
                    yield Button("Load", id="confirm", variant="primary")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
        else:
            value = self.query_one(Input).value.strip()
            self.dismiss(value or None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip() or None)


class _HistoryApp(App):
    """Textual application presenting git history for a single file."""

    CSS = DEFAULT_CSS
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("left", "prev_commit", "Previous", key_display="←"),
        Binding("right", "next_commit", "Next", key_display="→"),
        Binding("f", "prompt_file", "Select file", key_display="f"),
        Binding("tab", "focus_cycle", "Cycle focus", show=False),
    ]

    def __init__(
        self,
        repo: GitRepository,
        commits: Iterable[GitCommit],
        file_path: str,
        *,
        launch_cwd: str,
        limit: int,
    ) -> None:
        super().__init__()
        self.repo = repo
        self.commits: List[GitCommit] = list(commits)
        self.file_path = file_path
        self.launch_cwd = launch_cwd
        self.limit = limit
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

    def action_prompt_file(self) -> None:
        self.push_screen(FilePromptScreen(self.file_path), self._handle_file_selection)

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
        widths = self._compute_column_widths()
        diff_table = self._build_diff_table(diff.splitlines(), widths)
        self.detail_log.clear()
        self.detail_log.write(Group(meta, message, diff_table))
        self.detail_log.scroll_home()

    def _build_diff_table(self, lines: List[str], widths: tuple[int, int, int]) -> Table:
        removed_width, context_width, added_width = widths
        table = Table(
            show_header=True,
            header_style="bold",
            box=None,
            expand=True,
            pad_edge=False,
        )
        table.add_column(
            "Removed",
            style="red",
            width=removed_width,
            min_width=removed_width,
            max_width=removed_width,
            no_wrap=False,
            overflow="fold",
        )
        table.add_column(
            "Context",
            width=context_width,
            min_width=context_width,
            max_width=context_width,
            no_wrap=False,
            overflow="fold",
        )
        table.add_column(
            "Added",
            style="green",
            width=added_width,
            min_width=added_width,
            max_width=added_width,
            no_wrap=False,
            overflow="fold",
        )
        for raw in lines:
            line = raw.rstrip("\n")
            if line.startswith("diff --git"):
                table.add_row("", Text(line, style="cyan", overflow="fold"), "")
            elif line.startswith("@@"):
                table.add_row("", Text(line, style="yellow", overflow="fold"), "")
            elif line.startswith("---"):
                table.add_row(Text(line, style="red", overflow="fold"), "", "")
            elif line.startswith("+++"):
                table.add_row("", Text(line, style="green", overflow="fold"), "")
            elif line.startswith("-"):
                table.add_row(Text(line, style="red", overflow="fold"), "", "")
            elif line.startswith("+"):
                table.add_row("", "", Text(line, style="green", overflow="fold"))
            elif line.startswith("index"):
                table.add_row(Text(line, style="magenta", overflow="fold"), "", "")
            else:
                content = line[1:] if line.startswith(" ") else line
                table.add_row("", Text(content, overflow="fold"), "")
        return table

    def _compute_column_widths(self) -> tuple[int, int, int]:
        if self.detail_log and self.detail_log.size.width > 0:
            available = self.detail_log.size.width
        elif self.screen and self.screen.size.width > 0:
            available = self.screen.size.width
        else:
            available = 120
        usable = max(30, available - 6)
        third = max(10, usable // 3)
        return third, third, third

    def _select_index(self, index: int) -> None:
        if not self.commits:
            return
        index = max(0, min(len(self.commits) - 1, index))
        commit = self.commits[index]
        self._current_index = index
        self._show_commit(commit, index)

    def _handle_file_selection(self, file_path: str | None) -> None:
        if not file_path:
            return
        self._load_file(file_path)

    def _load_file(self, raw_path: str) -> None:
        try:
            abs_path, rel_path = self._resolve_file_input(raw_path)
        except ValueError as err:
            self._show_status(str(err), severity="warning")
            return
        try:
            commits = self.repo.list_file_commits(rel_path, limit=self.limit)
        except Exception as err:
            self._show_status(f"{err}", severity="error")
            return
        if not commits:
            self._show_status(f"No commits found for {rel_path}", severity="warning")
            return
        self.commits = commits
        self.file_path = rel_path
        self.title = f"git history: {rel_path}"
        self._current_index = 0
        self._select_index(0)
        self._show_status(f"Loaded {rel_path}", severity="information")

    def _resolve_file_input(self, raw: str) -> tuple[str, str]:
        path_str = raw.strip()
        if not path_str:
            raise ValueError("No file path provided.")
        if os.path.isabs(path_str):
            abs_path = os.path.abspath(path_str)
        else:
            abs_path = os.path.abspath(os.path.join(self.launch_cwd, path_str))
        if not os.path.exists(abs_path):
            raise ValueError(f"File does not exist: {abs_path}")
        if os.path.isdir(abs_path):
            raise ValueError("Path points to a directory; expected a file.")
        try:
            common = os.path.commonpath([self.repo.path, abs_path])
        except ValueError:
            common = ""
        if common != self.repo.path:
            raise ValueError(f"{abs_path} is outside repository {self.repo.path}")
        rel_path = os.path.relpath(abs_path, self.repo.path).replace(os.sep, "/")
        return abs_path, rel_path

    def _show_status(self, message: str, *, severity: str = "information") -> None:
        try:
            self.notify(message, severity=severity)
        except Exception:
            pass


class HistoryTUI:
    """Public interface mirroring the previous curses-based wrapper."""

    def __init__(
        self,
        repo: GitRepository,
        commits: Iterable[GitCommit],
        file_path: str,
        *,
        launch_cwd: str,
        limit: int,
    ) -> None:
        self._app = _HistoryApp(
            repo, list(commits), file_path, launch_cwd=launch_cwd, limit=limit
        )

    def run(self) -> None:
        self._app.run()
