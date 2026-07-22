---
title: Implement approval workflow system
status: open
labels: [wayfinder:security]
parent: .scratch/portcullis-hardening-map.md
blocked_by: []
---

## Question

How should the human-in-the-loop approval workflow be implemented with threshold options?

## Resolution Notes

**Decision:**
- Global approval_mode config: "always" | "first_only" | "never"
- Per-tool override via plugin metadata
- Default: "first_only" — first call to a tool/recipient needs approval, subsequent skip
- Use MCP prompt mechanism — tool returns a prompt asking user to approve
- Track approval state in memory (runtime only, not persistent)

**Implementation approach:**
1. Add approval_mode to Config class
2. Create approval state tracker (in-memory dict)
3. Wrap tool calls to check approval state
4. Return MCP prompt when approval needed: "Tool X called with args Y. Reply 'yes' to approve."
5. Handle approval response and execute or cancel

## Next Step

Design the approval state tracker and integrate into the tool call flow. Need to understand how MCP prompts work for interactive approval.
