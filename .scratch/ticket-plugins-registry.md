---
title: Create plugins.md registry
status: open
labels: [wayfinder:ux]
parent: .scratch/portcullis-hardening-map.md
blocked_by: []
---

## Question

What should the plugins.md registry file contain and how should the CLI read from it?

## Resolution Notes

**Decision:**
- plugins.md in repo root — curated markdown list
- Plugin authors submit via PR
- CLI command `portcullis plugins list-available` reads and displays
- Format: table with name, description, version, author, PyPI link

**Implementation approach:**
1. Create plugins.md with initial example plugin entry
2. Add CLI command to parse and display
3. Optionally: fetch latest version from PyPI when displaying

## Next Step

Create the initial plugins.md with the example plugin entry and implement the CLI list command.
