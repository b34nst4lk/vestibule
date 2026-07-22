# Domain Docs

## Layout

Single-context layout:
- `CONTEXT.md` at repo root — primary domain knowledge
- `docs/adr/` — Architecture Decision Records

## Reading CONTEXT.md

Read at session start to establish domain context. Use this file for:
- Domain terminology and concepts
- Key architectural constraints
- Important design decisions already made

## Reading ADRs

Location: `docs/adr/`

Format: `NNNN-short-title.md` (e.g., `0001-use-uv-package-manager.md`)

Read relevant ADRs when making architectural decisions that may relate to or conflict with prior decisions.

## Creating new ADRs

When making a significant architectural decision:
1. Create `docs/adr/NNNN-title.md` (next sequential number)
2. Follow the standard ADR template:
   - Title
   - Status (proposed, accepted, deprecated, superseded)
   - Context
   - Decision
   - Consequences
