# Git History TUI

Interactive terminal interface for browsing git repositories, inspired by [pomber/git-history](https://github.com/pomber/git-history).

## Features

- Displays recent commits with author and timestamp information.
- Arrow key navigation: use `Up`/`Down` to move through commits and `Left`/`Right` to switch focus between the commit list and details panel.
- View commit metadata, message body, and complete diff in the detail pane.
- Page up/down, home/end shortcuts for faster navigation.
- No avatars, no animations — just a fast, keyboard-driven TUI.

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

- `Left` / `Right`: move focus between commit list and details.
- `Up` / `Down`: move selection (list) or scroll (details).
- `PgUp` `PgDn`: page navigation.
- `Home` / `End` or `g` / `G`: jump to start/end of the list.
- `q`: quit.

## Development

Use `python -m githistory_tui /path/to/repo` during development without installing; just make sure `src/` is on `PYTHONPATH`:

```bash
PYTHONPATH=src python -m githistory_tui /path/to/repo
```

The curses UI works best in terminals that support basic color.
