from __future__ import annotations

import curses
from dataclasses import dataclass
from typing import Iterable, List, Literal

from .git_data import GitCommit, GitRepository

Focus = Literal["list", "detail"]


@dataclass
class ListEntry:
    label: str
    note: str
    timestamp: str


def shorten(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    if limit <= 1:
        return text[:limit]
    return text[: limit - 1] + "…"


class HistoryTUI:
    def __init__(self, repo: GitRepository, commits: Iterable[GitCommit]) -> None:
        self.repo = repo
        self.commits: List[GitCommit] = list(commits)
        self.selected_index = 0
        self.list_scroll = 0
        self.detail_scroll = 0
        self.focus: Focus = "list"
        self.status_message: str | None = None
        self._colors_enabled = False

    def _build_list_entry(self, commit: GitCommit) -> ListEntry:
        authored_at = commit.authored_at.strftime("%Y-%m-%d %H:%M")
        label = f"{commit.oid[:7]} {commit.title}"
        note = f"{commit.author_name} <{commit.author_email}>"
        return ListEntry(label=label, note=note, timestamp=authored_at)

    def _get_diff_lines(self, commit: GitCommit) -> List[str]:
        parent = commit.parent_oids[0] if commit.parent_oids else None
        diff = self.repo.get_diff(commit.oid, parent)
        return diff.splitlines()

    def _draw_list_panel(self, win: curses.window) -> None:
        height, width = win.getmaxyx()
        inner_height = max(0, height - 2)
        inner_width = max(0, width - 2)
        if not self.commits:
            win.addstr(1, 1, "No commits found", curses.A_DIM)
            return
        rows_per_entry = 3
        visible_rows = max(1, inner_height // rows_per_entry)
        max_scroll = max(0, len(self.commits) - visible_rows)
        self.list_scroll = max(0, min(self.list_scroll, max_scroll))
        if self.selected_index < self.list_scroll:
            self.list_scroll = self.selected_index
        elif self.selected_index >= self.list_scroll + visible_rows:
            self.list_scroll = self.selected_index - visible_rows + 1
        visible_indices = range(
            self.list_scroll, min(len(self.commits), self.list_scroll + visible_rows)
        )
        y = 1
        for idx in visible_indices:
            commit = self.commits[idx]
            entry = self._build_list_entry(commit)
            is_selected = idx == self.selected_index
            prefix = "> " if is_selected else "  "
            label = shorten(entry.label, inner_width)
            win.addstr(y, 1, shorten(prefix + label, inner_width), self._list_style(is_selected))
            if y + 1 < height - 1 and entry.note:
                note = shorten(entry.note, inner_width - 2)
                style = curses.A_DIM | self._list_style(is_selected)
                win.addstr(y + 1, 3, note, style)
            if y + 2 < height - 1:
                timestamp = shorten(entry.timestamp, inner_width - 2)
                style = curses.A_DIM | self._list_style(is_selected)
                win.addstr(y + 2, 3, timestamp, style)
            y += rows_per_entry

    def _list_style(self, is_selected: bool) -> int:
        attrs = curses.A_BOLD if self.focus == "list" and is_selected else curses.A_NORMAL
        if is_selected:
            attrs |= curses.A_REVERSE
        return attrs

    def _draw_detail_panel(self, win: curses.window) -> None:
        height, width = win.getmaxyx()
        inner_width = max(0, width - 2)
        inner_height = max(0, height - 2)
        if not self.commits:
            return
        commit = self.commits[self.selected_index]
        meta_lines = [
            f"commit {commit.oid}",
            f"Author: {commit.author_name} <{commit.author_email}>",
            f"Date:   {commit.authored_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
        if commit.body.strip():
            body_lines = [line.rstrip() for line in commit.body.splitlines()]
        else:
            body_lines = []
        diff_lines = self._get_diff_lines(commit)
        content_lines = meta_lines + body_lines + ([""] if body_lines else []) + diff_lines
        if self.detail_scroll >= len(content_lines):
            self.detail_scroll = max(0, len(content_lines) - 1)
        visible_lines = content_lines[self.detail_scroll : self.detail_scroll + inner_height]
        for row, line in enumerate(visible_lines):
            y = row + 1
            if y >= height - 1:
                break
            attr = curses.A_NORMAL
            if line.startswith("diff --git") or line.startswith("@@"):
                attr |= curses.A_BOLD
            elif line.startswith("+"):
                if self._colors_enabled:
                    attr |= curses.color_pair(2)
            elif line.startswith("-"):
                if self._colors_enabled:
                    attr |= curses.color_pair(3)
            win.addstr(y, 1, shorten(line, inner_width), attr)

    def _draw_border(self, win: curses.window, title: str, is_focused: bool) -> None:
        if is_focused:
            win.attron(curses.A_BOLD)
        win.box()
        win.addstr(0, 2, f" {title} ")
        if is_focused:
            win.attroff(curses.A_BOLD)

    def _draw_footer(self, stdscr: curses.window, message: str) -> None:
        height, width = stdscr.getmaxyx()
        stdscr.attron(curses.A_REVERSE)
        if height > 0 and width > 0:
            stdscr.addstr(height - 1, 0, shorten(message.ljust(width), width))
        stdscr.attroff(curses.A_REVERSE)

    def run(self) -> None:
        curses.wrapper(self._main_loop)

    def _main_loop(self, stdscr: curses.window) -> None:
        curses.curs_set(0)
        stdscr.keypad(True)
        self._init_colors()
        stdscr.nodelay(False)
        while True:
            stdscr.clear()
            height, width = stdscr.getmaxyx()
            list_width = max(30, width // 3)
            detail_width = width - list_width
            list_win = stdscr.subwin(max(2, height - 1), max(4, list_width), 0, 0)
            detail_win = stdscr.subwin(
                max(2, height - 1), max(4, detail_width), 0, list_width
            )
            list_win.clear()
            detail_win.clear()
            self._draw_border(list_win, "Commits", self.focus == "list")
            self._draw_border(detail_win, "Details", self.focus == "detail")
            self._draw_list_panel(list_win)
            self._draw_detail_panel(detail_win)
            footer = (
                self.status_message
                or "UP/DOWN select  LEFT/RIGHT focus  PgUp/PgDn scroll  q quit"
            )
            self._draw_footer(stdscr, footer)
            stdscr.refresh()
            list_win.refresh()
            detail_win.refresh()

            ch = stdscr.getch()
            if ch == ord("q"):
                break
            if ch in (curses.KEY_LEFT, curses.KEY_RIGHT):
                self.focus = "list" if ch == curses.KEY_LEFT else "detail"
                self.status_message = None
            elif ch in (curses.KEY_UP, curses.KEY_DOWN):
                self._handle_vertical(ch)
            elif ch in (curses.KEY_NPAGE, curses.KEY_PPAGE):
                self._handle_page(ch, max(1, height - 4))
            elif ch in (curses.KEY_HOME, ord("g")):
                self._go_to(0)
            elif ch in (curses.KEY_END, ord("G")):
                self._go_to(len(self.commits) - 1)
            elif ch != -1:
                self.status_message = "Press q to quit"

    def _init_colors(self) -> None:
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(2, curses.COLOR_GREEN, -1)
            curses.init_pair(3, curses.COLOR_RED, -1)
            self._colors_enabled = True
        else:
            self._colors_enabled = False

    def _handle_vertical(self, ch: int) -> None:
        if self.focus == "list":
            delta = -1 if ch == curses.KEY_UP else 1
            new_index = max(0, min(len(self.commits) - 1, self.selected_index + delta))
            if new_index != self.selected_index:
                self.selected_index = new_index
                self.detail_scroll = 0
            self.status_message = None
        else:
            delta = -1 if ch == curses.KEY_UP else 1
            self.detail_scroll = max(0, self.detail_scroll + delta)
            self.status_message = None

    def _handle_page(self, ch: int, page_size: int) -> None:
        if self.focus == "list":
            delta = -page_size if ch == curses.KEY_PPAGE else page_size
            self._go_to(max(0, min(len(self.commits) - 1, self.selected_index + delta)))
        else:
            delta = -page_size if ch == curses.KEY_PPAGE else page_size
            self.detail_scroll = max(0, self.detail_scroll + delta)
        self.status_message = None

    def _go_to(self, index: int) -> None:
        if not self.commits:
            return
        index = max(0, min(len(self.commits) - 1, index))
        if index != self.selected_index:
            self.selected_index = index
            self.detail_scroll = 0
        self.status_message = None
