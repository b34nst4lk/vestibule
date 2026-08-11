# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**vestibule** is a new Python 3.13 project using `uv` for package management. The project is in its initial scaffold stage.

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
- `README.md` is populated — keep it in sync as features are added

## FastMCP integration notes

These are hard-won facts about the `mcp` library (FastMCP). Read the public API
surface and source before touching library internals — do not reach into
`_private` attributes.

- **Version:** `mcp>=1.28.1` (see `pyproject.toml`). Re-validate these notes when
  bumping the dependency.
- **Upstream docs:** https://github.com/modelcontextprotocol/python-sdk

### Public API surface (use these, not private attrs)

- `list_tools()` — returns registered tools (use for existence checks)
- `call_tool(name, arguments)` — invoke a tool
- `add_tool()` / `remove_tool()` / `tool()` — register/unregister
- `list_prompts()`, `list_resources()`, `read_resource()`, `get_prompt()`

### Error-wrapping behavior (critical)

- FastMCP wraps **all** tool exceptions — pydantic argument-validation errors
  AND `TypeError` — into `ToolError("Error executing tool {name}: ...")`.
- Consequence: argument-validation errors are **not** `INVALID_PARAMS`; they
  surface as `ToolError`. A `TypeError` branch in a handler is only reachable via
  a non-FastMCP fallback path (e.g. calling `tool.handler(**args)` directly).
- To distinguish protocol errors from business errors, pre-check tool existence
  (via `list_tools()`) and raise `ToolError` for unknown tools so the transport
  maps it to `method_not_found`.

### Output-model wrapping (critical)

- A default `-> str` FastMCP tool auto-wraps its return into a validated output
  model (`wrap_output=True`). Returning a `CallToolResult` from such a tool
  **fails** validation.
- To return `CallToolResult` directly (e.g. business errors as
  `CallToolResult(content=[TextContent(...)], isError=True)`), register the tool
  with `structured_output=False`.

### Adapter pattern

Centralize all FastMCP interaction (tool existence, tool call, result
extraction) behind a thin adapter in `vestibule/transports/common.py` so upstream
changes are contained. If you must touch internals, isolate them and add a test
that pins the behavior — an upstream change should surface as a failing test,
not a silent break.

## Coding style: ponytail (always-on, default `full`)

Write the laziest solution that actually works. The best code is the code never written. Climb this ladder before writing anything, stop at the first rung that holds:

1. **Does this need to exist?** Speculative need = skip it. (YAGNI)
2. **Already in this codebase?** Reuse the existing helper/util/pattern.
3. **Stdlib does it?** Use it.
4. **Native platform feature?** Use it.
5. **Already-installed dependency solves it?** Use it; never add a new dep for a few lines.
6. **Can it be one line?** One line.
7. **Only then:** the minimum code that works.

The ladder runs *after* understanding the problem, not instead of it: read the code the change touches, trace the real flow first. Lazy about the solution, never about reading.

Rules:
- No unrequested abstractions (interface with one impl, factory for one product, config for a constant).
- Deletion over addition. Boring over clever. Fewest files, shortest working diff.
- Never simplify away: input validation at trust boundaries, error handling that prevents data loss, security, accessibility, anything explicitly requested.
- Bug fix = root cause, not symptom. Grep every caller of the function you're about to touch; fix once where all callers route through.
- Mark a deliberate shortcut with a `ponytail:` comment naming the ceiling + upgrade path.
- Non-trivial logic leaves ONE runnable check (an `assert`-based self-check or one small `test_*.py`). No frameworks/fixtures unless asked.
- Explanation shorter than the code is debt; delete it. Only explain what was skipped and when to add it.

The full skill (intensity levels, review/audit commands) is available as `/skill:ponytail`.

## Verbosity

Be terse. Give the answer, the diff, and at most a few short lines of rationale. No feature tours, no status recaps, no praise, no hedging prose, no "let me know if...". Match the brevity of the code you write.

## Engineering conventions

- **Verify runtime behavior before writing tests/assertions.** FastMCP's wrapping
  can make a code path unreachable in ways that aren't obvious. Probe with a
  quick `uv run python -c "..."` before assuming a branch is exercised.
- **Run Sourcery review and address it before merging**, while the code is still
  in the PR — not after.
- **Do NOT auto-merge PRs.** Open the PR, get CI + Sourcery green, then leave
  the merge to the user (or to their explicit go-ahead).
- **`gh` keyring times out** — run `export GH_TOKEN=$(gh auth token)` before gh
  commands.
- **`.coverage` is a tracked binary** that changes on every test run. It is now
  gitignored; if it ever gets re-added, run `git rm --cached .coverage` so the
  ignore rule takes effect.

## Agent skills

### Issue tracker

Issues are tracked as local markdown files under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout: `CONTEXT.md` + `docs/adr/` at repo root. See `docs/agents/domain.md`.
