---
title: Implement audit logging infrastructure
status: open
labels: [wayfinder:security]
parent: .scratch/portcullis-hardening-map.md
blocked_by: []
---

## Question

How should the audit logging infrastructure be implemented to log all tool calls with comprehensive detail while masking secrets via Pydantic's SecretStr?

## Resolution Notes

**Decision:**
- Log format: Structured JSON to stdout
- Fields: tool_name, timestamp, session_id, success/failure, masked_arguments
- Secret masking: Use Pydantic SecretStr type — plugin authors mark sensitive fields, __repr__/__str__ output "***"
- No retention built-in — user's infrastructure concern

**Implementation approach:**
1. Add logging dependency (structlog or stdlib logging with JSON formatter)
2. Create audit logger module in portcullis/
3. Wrap tool call handlers to emit audit logs
4. Add SecretStr import to hooks.py for plugin authors to use

## Next Step

Implement the audit logging module and integrate into both transports. Start with a simple JSON formatter using stdlib logging, then add SecretStr support.
