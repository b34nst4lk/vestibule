---
title: Update naming consistency to Portcullis
status: closed
labels: [wayfinder:publishing]
parent: .scratch/portcullis-hardening-map.md
blocked_by: []
resolved: Replaced all Bulwark → Portcullis in CLAUDE.md, portcullis/*.py docstrings, .scratch/ tickets, and env var names (BULWARK_DATA_DIR → PORTCULLIS_DATA_DIR). 0 Bulwark references remaining.
---

## Question

Where are all the Bulwark references that need to be updated to Portcullis?

## Resolution Notes

**Files updated:**
- CLAUDE.md — project description
- .scratch/*.md — all ticket files and research notes
- portcullis/__init__.py, config.py, hooks.py, transports/__init__.py — docstrings
- .scratch/research-integration-testing.md — env var names

**Implementation:**
- Used sed to replace Bulwark → Portcullis (case-insensitive)
- BULWARK_DATA_DIR → PORTCULLIS_DATA_DIR in test code snippets
- Verified with grep: 0 Bulwark references remaining

**Commit:** f79d939
