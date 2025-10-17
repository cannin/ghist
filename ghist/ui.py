from __future__ import annotations

import os
from collections import defaultdict
from textwrap import wrap
from typing import Iterable, List

from rich.console import Group
from rich.table import Table
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, RichLog, Static

from .git_data import GitCommit, GitRepository, GitError


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
        self._header_widths: tuple[int, int] | None = None
        self._header_height: int | None = None
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
        self._header_widths = None
        self._header_height = None
        self._select_index(0)
        self.call_after_refresh(self._refresh_current_commit)
        self.set_focus(self.detail_log)

    def action_prev_commit(self) -> None:
        if not self.commits:
            return
        new_index = min(len(self.commits) - 1, self._current_index + 1)
        self._select_index(new_index)

    def action_next_commit(self) -> None:
        if not self.commits:
            return
        new_index = max(0, self._current_index - 1)
        self._select_index(new_index)

    def action_prompt_file(self) -> None:
        self.push_screen(FilePromptScreen(self.file_path), self._handle_file_selection)

    def on_resize(self, event: events.Resize) -> None:
        self._header_widths = None
        self._header_height = None
        self.call_after_refresh(self._refresh_current_commit)

    def _show_commit(self, commit: GitCommit, index: int) -> None:
        assert self.detail_log is not None
        total = len(self.commits)
        message = Text(justify="left")
        if commit.title:
            message.append(f"{commit.title}\n", style="italic")
        if commit.body.strip():
            message.append(commit.body.rstrip() + "\n")

        info = Text(justify="left")
        info.append(f"commit: {commit.oid}\n")
        info.append(f"author: {commit.author_name} <{commit.author_email}>\n")
        info.append(f"date: {commit.authored_at.strftime('%Y-%m-%d %H:%M:%S')}\n")
        info.append(f"file: {self.file_path}\n")
        info.append(f"position: {total - index}/{total} commits")

        left_width, right_width = self._compute_header_widths()
        header_height = self._compute_header_height()
        info = self._fit_text_height(info, header_height, left_width)
        message = self._fit_text_height(message, header_height, right_width)
        header = Table.grid(expand=False, pad_edge=False)
        header.add_column(
            width=left_width,
            min_width=left_width,
            max_width=left_width,
            overflow="fold",
            no_wrap=False,
        )
        header.add_column(
            width=right_width,
            min_width=right_width,
            max_width=right_width,
            overflow="fold",
            no_wrap=False,
        )
        header.add_row(info, message)

        (
            file_lines,
            file_error,
            add_count,
            del_count,
            added_lines,
            removed_before,
        ) = self._prepare_context(commit)
        context = self._build_context_text(
            file_lines, file_error, add_count, del_count, added_lines, removed_before
        )
        self.detail_log.clear()
        self.detail_log.write(Group(header, Text("\n"), context))
        self.detail_log.scroll_home()

    def _prepare_context(
        self, commit: GitCommit
    ) -> tuple[List[str], str | None, int, int, set[int], dict[int, List[tuple[int, str]]]]:
        try:
            file_text = self.repo.get_file_contents(commit.oid, self.file_path)
            file_lines = file_text.splitlines()
            file_error: str | None = None
        except GitError as err:
            file_lines = []
            file_error = str(err)
        parent = commit.parent_oids[0] if commit.parent_oids else None
        diff_lines = self.repo.get_file_diff(commit.oid, self.file_path, parent).splitlines()
        added_lines: set[int] = set()
        removed_before: dict[int, List[tuple[int, str]]] = defaultdict(list)
        add_count = del_count = 0
        current_old = current_new = 0
        for line in diff_lines:
            if line.startswith("@@"):
                try:
                    header = line.split("@@")[1].strip()
                    old_part, new_part = header.split(" ")
                except ValueError:
                    old_part, new_part = "-1,0", "+1,0"
                old_start = int(old_part.split(",")[0].replace("-", ""))
                new_start = int(new_part.split(",")[0].replace("+", ""))
                current_old = old_start
                current_new = new_start
                continue
            if line.startswith("diff ") or line.startswith("index"):
                continue
            if line.startswith("---") or line.startswith("+++"):
                continue
            if line.startswith("-"):
                key = current_new if current_new else 1
                removed_before[key].append((current_old, line[1:]))
                current_old += 1
                del_count += 1
            elif line.startswith("+"):
                key = current_new if current_new else 1
                added_lines.add(key)
                current_new += 1
                add_count += 1
            elif line.startswith(" "):
                current_old += 1
                current_new += 1
        return file_lines, file_error, add_count, del_count, added_lines, removed_before
    def _build_context_text(
        self,
        file_lines: List[str],
        file_error: str | None,
        add_count: int,
        del_count: int,
        added_lines: set[int],
        removed_before: dict[int, List[tuple[int, str]]],
    ) -> Text:
        text = Text()
        header = Text.assemble(
            ("Edited ", ""),
            (self.file_path, ""),
            (" (", ""),
            (f"+{add_count}", "green"),
            (", ", ""),
            (f"-{del_count}", "red"),
            (")\n", ""),
        )
        text.append(header)
        text.append("\n")
        if file_error:
            text.append("Unable to load current file:\n", style="bold red")
            text.append(f"{file_error}\n")
            return text
        final_key = len(file_lines) + 1
        for line_no in range(1, len(file_lines) + 1):
            for old_line, removed_text in removed_before.pop(line_no, []):
                text.append(f"{old_line:5d} -{removed_text}\n", style="red")
            line_text = file_lines[line_no - 1]
            if line_no in added_lines:
                text.append(f"{line_no:5d} +{line_text}\n", style="green")
            else:
                text.append(f"{line_no:5d}  {line_text}\n")
        for old_line, removed_text in removed_before.pop(final_key, []):
            text.append(f"{old_line:5d} -{removed_text}\n", style="red")
        for remaining in removed_before.values():
            for old_line, removed_text in remaining:
                text.append(f"{old_line:5d} -{removed_text}\n", style="red")
        return text

    def _compute_header_widths(self) -> tuple[int, int]:
        if self._header_widths and all(w > 0 for w in self._header_widths):
            return self._header_widths
        available = 0
        if self.detail_log and self.detail_log.size.width > 0:
            available = self.detail_log.size.width
        elif self.screen and self.screen.size.width > 0:
            available = self.screen.size.width
        if available <= 0:
            available = 120
        usable = max(40, available - 4)
        left = max(20, (usable * 3) // 5)
        right = max(15, usable - left)
        self._header_widths = (left, right)
        return self._header_widths

    def _compute_header_height(self) -> int:
        if self._header_height and self._header_height > 0:
            return self._header_height
        self._header_height = 6
        return self._header_height

    def _fit_text_height(self, text: Text, height: int, width: int) -> Text:
        raw_lines = text.plain.splitlines() or [""]
        wrapped: List[str] = []
        max_width = max(1, width - 1)
        for line in raw_lines:
            if not line:
                wrapped.append("")
                continue
            wrapped.extend(wrap(line, max_width) or [""])
        if len(wrapped) < height:
            wrapped.extend([""] * (height - len(wrapped)))
        else:
            wrapped = wrapped[:height]
        return Text("\n".join(wrapped), justify="left")

    def _refresh_current_commit(self) -> None:
        if not self.commits or self.detail_log is None:
            return
        self._show_commit(self.commits[self._current_index], self._current_index)

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
        self._header_widths = None
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
