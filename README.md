# Git History TUI

Interactive [Textual](https://github.com/Textualize/textual)-based interface for browsing git repositories, inspired by [pomber/git-history](https://github.com/pomber/git-history).

## Features

- Displays recent commits with author and timestamp information.
- Textual widgets with keyboard navigation: use `Left`/`Right` to step through commits and `Up`/`Down` to inspect the timeline.
- View commit metadata, message body, and complete diff in the detail pane.
- Page up/down, home/end shortcuts for faster navigation.
- No avatars, no animations — just a fast, keyboard-driven TUI.
- Side-by-side diff visualization that keeps removed lines on the left, resulting file content in the center, and incoming additions on the right.

## Installation

The project uses a standard `pyproject.toml` (`setuptools` based). You can run it in-place or install it in an isolated environment:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
```

## Usage

```bash
githistory-tui path/to/git/repo
```

The path must point to a directory that contains a `.git` folder (or pass nothing to target the current directory). Optional flags:

- `--limit`: number of commits to load (defaults to 256).

Inside the interface:
- `Left` / `Right`: move to the previous or next commit.
- `Up` / `Down`: move within the commit list (when focused) or scroll the detail view.
- `PgUp` `PgDn`: page navigation.
- `Home` / `End` or `g` / `G`: jump to start/end of the list.
- `q`: quit.

## Development

Use `python -m githistory_tui /path/to/repo` during development without installing; just make sure `src/` is on `PYTHONPATH` and that `textual` is available:

```bash
PYTHONPATH=src python -m githistory_tui /path/to/repo
```

The Textual UI works best in terminals that support basic color.
