---
title: Refactor transport duplication
status: open
labels: [wayfinder:code-quality]
parent: .scratch/portcullis-hardening-map.md
blocked_by: []
---

## Question

How should the duplicated handlers between stdio.py and http_sse.py be extracted into common.py?

## Resolution Notes

**Decision:**
- Functional extraction (not base class)
- Move to common.py: _handle_initialize, _handle_ping, _handle_resources_list, _handle_resources_read, _handle_prompts_list, _handle_prompts_get
- Both transports import and use shared handlers
- Transport-specific logic stays in各自 files (session management, HTTP routing, stdio streaming)

**Implementation approach:**
1. Copy duplicated functions to common.py
2. Update imports in stdio.py and http_sse.py
3. Verify tests still pass
4. Remove duplicated code

## Next Step

Extract the handlers to common.py and update both transports to import from there. Run tests to verify.
