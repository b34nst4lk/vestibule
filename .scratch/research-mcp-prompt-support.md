---
title: Research MCP prompt support across clients
status: closed
labels: [wayfinder:research]
parent: .scratch/portcullis-hardening-map.md
blocked_by: []
resolved: Key finding: use elicitation (elicitation/create), not prompts. Hermes has full support; Claude Code has bugs in recent versions. See full findings below.
---

## Question

Which MCP clients support interactive prompts, and how do they handle the prompt/response flow?

## Resolution Notes

### Key Finding: Elicitation, Not Prompts

**Prompts** (`prompts/list`, `prompts/get`) are user-controlled templates for pre-execution context.

**Elicitation** (`elicitation/create`) is server-initiated, mid-execution input with `accept`/`decline`/`cancel` semantics — this is the correct mechanism for approval workflows.

### Client Support Summary

| Feature | Hermes | Claude Code |
|---------|--------|-------------|
| Prompts | ✅ Supported | ✅ Supported |
| Elicitation | ✅ Full support | ⚠️ Supported with bugs |
| Form-mode | ✅ Working | ⚠️ Auto-decline bug (v2.1.144+) |
| URL-mode | ❌ Not supported | ⚠️ Broken since ~v2.1.108 |
| Mid-tool-call | ✅ Yes | ⚠️ Yes (with bugs) |

### Recommended Implementation

1. Use form-mode elicitation (URL mode unreliable)
2. Keep schemas simple (flat objects, primitive types)
3. Handle all three actions: `accept`, `decline`, `cancel`
4. Add `anthropic/requiresUserInteraction` metadata for Claude Code
5. Check client capabilities during initialization
6. Design fail-closed fallbacks

### Sources

- [MCP Elicitation Spec](https://modelcontextprotocol.io/specification/2025-06-18/client/elicitation)
- [Hermes Elicitation Handler](https://github.com/NousResearch/hermes-agent/pull/49203)
- [Claude Code Issue #62319 (auto-decline bug)](https://github.com/anthropics/claude-code/issues/62319)
- [Claude Code Issue #69555 (URL-mode broken)](https://github.com/anthropics/claude-code/issues/69555)

## Next Step

Implement approval workflow using elicitation. Note: Claude Code has active bugs — test primarily with Hermes.
