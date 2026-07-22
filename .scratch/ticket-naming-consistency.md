---
title: Update naming consistency to Portcullis
status: open
labels: [wayfinder:publishing]
parent: .scratch/portcullis-hardening-map.md
blocked_by: []
---

## Question

Where are all the [Pp]ortcullis references that need to be updated to Portcullis?

## Resolution Notes

**Files to update:**
- CLAUDE.md — project description
- .scratch/*.md — all ticket files
- Code comments in main.py, portcullis/*.py
- Any remaining docs

**Implementation approach:**
1. grep -r "portcullis" --include="*.md" --include="*.py" .scratch/
2. Replace with "portcullis" (case-insensitive where appropriate)
3. Verify pyproject.toml already has correct name

## Next Step

Run grep to find all [Pp]ortcullis references and systematically replace them.
