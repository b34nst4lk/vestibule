---
title: Fix README PyPI claims
status: closed
labels: [wayfinder:publishing]
parent: .scratch/portcullis-hardening-map.md
blocked_by: []
resolved: Added v0.1.0 Beta banner, updated installation to uv sync from source, clarified email plugin is workspace-only, removed example plugin section (not yet created)
---

## Question

What false claims in the README need to be corrected before 0.1.0 publication?

## Resolution Notes

**Changes made:**
- Added `> **v0.1.0 Beta** — Initial release. Installation via uv from source (not yet on PyPI).` banner
- Updated installation section to use `git clone` + `uv sync`
- Removed `pip install portcullis` and `pip install portcullis-email` references
- Added note that email plugin is workspace-only, PyPI package coming later
- Removed example plugin section (not yet created)

**Files changed:**
- `README.md` — Updated installation, features, and plugin sections

**Commit:** Pending

## Next Step

README is ready for 0.1.0. Next: create the example plugin package.
