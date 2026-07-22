---
title: Fix README PyPI claims
status: open
labels: [wayfinder:publishing]
parent: .scratch/portcullis-hardening-map.md
blocked_by: []
---

## Question

What false claims in the README need to be corrected before 0.1.0 publication?

## Resolution Notes

**Issues to fix:**
- "pip install portcullis" — not on PyPI yet
- "pip install portcullis-email" — not published for 0.1.0
- Update installation instructions to reflect source install
- Add 0.1.0 disclaimer about beta status

**Implementation approach:**
1. Update Quick Start section with uv/source install instructions
2. Add note about 0.1.0 beta status
3. Clarify example plugin is included, email plugin is workspace-only

## Next Step

Rewrite the README Quick Start and Installation sections to reflect 0.1.0 reality.
