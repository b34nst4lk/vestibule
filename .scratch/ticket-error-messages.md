---
title: Improve error message consistency
status: open
labels: [wayfinder:ux]
parent: .scratch/portcullis-hardening-map.md
blocked_by: []
---

## Question

How should error messages be standardized across the codebase?

## Resolution Notes

**Decision:**
- Rely on MCP framework defaults for plugin error handling
- Document the hybrid approach:
  - Protocol errors (method not found, parse errors) → JSON-RPC error object
  - Business logic errors (recipient not found, rate limited) → content with isError: true
- No additional Portcullis-specific error layer for 0.1.0

**Implementation approach:**
1. Document error handling conventions in README/docs
2. Review existing error paths for consistency
3. Ensure both transports follow the same pattern

## Next Step

Review current error handling in both transports and align to the documented convention. Add documentation to README.
