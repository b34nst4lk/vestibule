---
title: Refactor transport duplication
status: closed
labels: [wayfinder:code-quality]
parent: .scratch/portcullis-hardening-map.md
blocked_by: []
resolved: Extracted 6 shared handlers (initialize, initialized, resources_list, resources_read, prompts_list, prompts_get, ping) + JSON-RPC error codes to common.py. Both stdio.py and http_sse.py now import and delegate. 66 tests pass. Commit: 058750a
---

## Question

How should the duplicated handlers between stdio.py and http_sse.py be extracted into common.py?

## Resolution Notes

**Decision:**
- Functional extraction (not base class)
- Move to common.py: handle_initialize, handle_initialized, handle_resources_list, handle_resources_read, handle_prompts_list, handle_prompts_get, handle_ping
- Both transports import and use shared handlers
- Transport-specific logic stays in各自 files (session management, HTTP routing, stdio streaming)

**Implementation:**
- Added shared handlers to `portcullis/transports/common.py`
- Added JSON-RPC error codes to common.py (PARSE_ERROR, INVALID_REQUEST, etc.)
- Updated stdio.py and http_sse.py to import from common.py
- All 66 tests pass

**Files changed:**
- `portcullis/transports/common.py` — Added 6 handlers + error codes
- `portcullis/transports/stdio.py` — Now imports/delegates to common.py
- `portcullis/transports/http_sse.py` — Now imports/delegates to common.py

**Commit:** 058750a
