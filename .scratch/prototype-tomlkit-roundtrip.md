# Prototype: tomlkit round-trip editing for vestibule config

**Ticket:** #24 (map #9) — COMPLETED
**Date:** current session

## Question
Can `tomlkit` perform per-key round-trip edits on Vestibule's config structure
without clobbering comments, formatting, or ordering?

## Verdict
**Yes.** `tomlkit` handles all the operations the `vestibule config` CLI needs.
Prototype script exercised against the example config structure.

## Findings
- **Set a key in a nested table** (`[tool.vestibule.plugins.email]`) — works;
  comments, blank lines, and key ordering preserved.
- **Set a key inside an inline table** (`whitelist`) — works; appends cleanly.
- **Unset a key** — works; removes the key, preserves everything else.
- **Unset a whole section** — works; removes the table.
- **Atomic write** (temp file + `os.replace`) — works with tomlkit output.

## Gotcha (cosmetic)
When adding a **new** key to a table that has a sub-table, tomlkit appends the
key after the last comment block in that table. So a comment intended for a
sub-table header can get separated from it. Example: adding `sender_name` to
`[tool.vestibule.plugins.email]` placed it between the `# Whitelist:` comment
and the `[tool.vestibule.plugins.email.whitelist]` header. TOML stays valid;
it's purely cosmetic. The CLI can accept this, or insert at a specific index
(tomlkit supports positional insert) if we want to avoid it.

## Dependency
`tomlkit` (0.15.1) verified. **Not committed** — the prototype is throwaway.
Add `tomlkit` via `uv add tomlkit` in ticket #26 (Implement vestibule config
CLI), where it is actually consumed.
