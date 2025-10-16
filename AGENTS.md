# Agent Usage Notes

- Preferred execution method: `uv run python -m ghist <file-path>` (pass an absolute or relative path to the tracked file). The package now lives at the repository root, so no extra `PYTHONPATH` tweaks are needed in the transient environment.
- When adjusting documentation or onboarding instructions, keep the README and this file aligned on the recommended `uv run` workflow.
- Avoid introducing animated effects in the TUI; focus on clear color-coding (green for additions, red for deletions) and keyboard navigation via arrow keys.
