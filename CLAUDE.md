# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**portcullis** is a new Python 3.13 project using `uv` for package management. The project is in its initial scaffold stage.

## Commands

```bash
# Run the application
uv run python main.py

# Add a dependency
uv add <package-name>

# Add a dev dependency
uv add --dev <package-name>

# Run a command in the project environment
uv run <command>
```

## Architecture

- **Entry point**: `main.py` — currently a minimal scaffold printing a greeting
- **Configuration**: `pyproject.toml` — defines project metadata and dependencies (PEP 621)
- **Python version**: 3.13 (specified in `.python-version`)

## Notes

- The project uses `uv` — prefer `uv run`, `uv add` over `pip` and `python` directly
- `README.md` is empty — populate with project documentation as features are added

## Agent skills

### Issue tracker

Issues are tracked as local markdown files under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout: `CONTEXT.md` + `docs/adr/` at repo root. See `docs/agents/domain.md`.
