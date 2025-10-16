# Git History TUI

Interactive [Textual](https://github.com/Textualize/textual)-based interface for exploring the history of a single file in a git repository, inspired by [pomber/git-history](https://github.com/pomber/git-history).

## Features

- Displays the commits that touched a given file with author and timestamp information.
- Textual widgets with keyboard navigation: use `Left`/`Right` to step through commits and `Up`/`Down` to scroll the diff.
- View commit metadata, message body, and complete diff in the detail pane.
- Page up/down, home/end shortcuts for faster navigation.
- No avatars, no animations — just a fast, keyboard-driven TUI.
- Side-by-side diff visualization with deleted lines in red (left), context in the middle, and inserted lines in green (right).

## Installation

The project uses a standard `pyproject.toml` (`setuptools` based). You can run it in-place or install it in an isolated environment:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
```

## Usage

Preferred quick-run (no install needed) using [uv](https://github.com/astral-sh/uv):

```bash
uv run python -m githistory_tui path/to/git/repo/README.md
```

If you have already installed the project (or prefer the console script), you can run:

```bash
githistory-tui path/to/git/repo/README.md
```

The path must point to a tracked file inside a git repository. Optional flags:

- `--limit`: number of commits to load (defaults to 256).

Inside the interface:
- `Left` / `Right`: move to the previous or next commit.
- `Up` / `Down`: scroll the detail view.
- `PgUp` `PgDn`: page navigation.
- `Home` / `End` or `g` / `G`: jump to start/end of the list.
- `q`: quit.

## Development

Use `uv run python -m githistory_tui /absolute/path/to/file` during development for an isolated environment with dependencies resolved automatically.

The Textual UI works best in terminals that support basic color.
