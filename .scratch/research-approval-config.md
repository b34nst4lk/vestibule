# Research: Approval Configuration in Plugin-Based Systems

## Summary / Recommendation

**How much control should the user get, given the plugin provides good defaults?**

Across every primary source surveyed, the dominant pattern is:

> **The plugin/tool author declares the approval requirement (the default); the operator/user can override it via config — in both directions (tighten and loosen).**

Concretely for Vestibule:

1. **Plugin declares per-tool approval policy** (via a hook) — this is the "good defaults" the plugin author provides, co-located with the tool definitions.
2. **Config is a thin layer**: a global `enabled` switch plus **per-tool / per-plugin overrides** for the operator. Overrides are the *exception*, not the primary mechanism.
3. **Fail closed**: if a tool is declared sensitive but no approval mechanism is active, the server should refuse to run it (or refuse to build) rather than silently allow. On approval timeout, deny by default.
4. **Risk-based defaults**: read-only tools default to allow; anything that writes, sends, deletes, or spends defaults to require approval.

This resolves the earlier design tension: the plugin owns the policy (co-located, no magic strings in a global section), and the operator still has an escape hatch — which the research shows operators genuinely need.

---

## MCP Specification (primary)

**Source:** [MCP spec — Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools), [MCP spec — Authorization](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization)

- "For trust & safety and security, there **SHOULD** always be a human in the loop with the ability to deny tool invocations." (Tools page, User Interaction Model)
- Tools carry `annotations` (`destructiveHint`, `readOnlyHint`, `openWorldHint`) — explicitly **hints for UX/behavior, not security controls**. Clients "MUST consider tool annotations to be untrusted unless they come from trusted servers."
- The tool set "MAY vary by the authorization presented on the request" — i.e., per-request authorization can filter which tools are visible/usable.
- MCP's own authorization is OAuth 2.1 at the transport level (HTTP only); stdio "SHOULD NOT" use it and instead "retrieve credentials from the environment." So for a stdio/local server, approval is a server-side concern, not an OAuth concern.

**SEP-1880 (tool-level scopes)** — [closed proposal](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1880). The most relevant comment (IkaRiche):

> "Tool-level scopes define *what constraints exist*, but they still don't answer whether this specific action proposed by the model should execute immediately, require human confirmation, or be blocked under current runtime policy... the intent must pass through a deterministic gate that decides the outcome (`ALLOW / REQUIRE_CONFIRM / BLOCK`)."

This is the strongest signal: **approval is a runtime gate on the tool, distinct from static scope/annotation metadata.** The gate is the enforcement point.

---

## OpenAI Agents SDK — Human-in-the-loop (primary)

**Source:** [OpenAI Agents SDK — Human-in-the-loop](https://openai.github.io/openai-agents-python/human_in_the_loop/)

- **Tools declare when they need approval**: `@tool(needs_approval=True)` (always) or a callable that decides per call.
- The callable "fails closed when the SDK cannot safely inspect the arguments" — malformed args → manual approval required.
- **Operator override at runtime**: `state.approve(interruption, always_approve=True)` / `always_reject=True` persist the decision for future calls to that tool during the run.
- Approval is per-call by default; `always_approve`/`always_reject` are the sticky override.

**Pattern:** tool-declared default + runtime operator override (sticky). The tool author sets the default; the operator can loosen or tighten.

---

## Promptise Foundry — Approval Gates (primary)

**Source:** [Promptise Foundry — Approval Gates](https://docs.promptise.com/mcp/server/approval-gates/)

- "A gate in the server's middleware chain makes approval **a property of the tool**, not a courtesy of the caller."
- Tool declares `requires_approval=True`; the gate enforces it for **any** MCP client.
- **Fail-closed at build time**: "If any tool declares `requires_approval=True` and no `ApprovalGateMiddleware` is installed, the server raises at build time... A declared approval that silently doesn't enforce would be worse than none."
- **Fail-closed on timeout**: no decision within `timeout` → denied by default (`on_timeout="allow"` opts out explicitly).
- Gate checks the tool's own guards (auth/role) *before* requesting a human decision, so unauthorized callers can't spam approvers.

**Pattern:** tool-declared, fail-closed, enforced server-side. Strongest argument for "declared approval must be enforced or the build fails."

---

## HookWatch — MCP Approvals (primary)

**Source:** [HookWatch — MCP Approvals](https://docs.hookwatch.dev/mcp-proxy/approvals)

- Per-server `approval_config`: `enabled`, `default_action` (require/allow), `trust_level`, `ttl_seconds`, `rules` (ordered glob patterns, first match wins).
- **Trust levels as good defaults**:
  - `strict` — falls back to `default_action` (maximum oversight)
  - `moderate` — read tools `allow`, write tools `require`, destructive tools `require`
  - `autonomous` — allow all (rate limits/budgets still apply)
- Tools are categorized `read` / `write` / `destructive`; moderate trust uses the category to decide.
- Pending approvals expire after TTL (default 300s).

**Pattern:** config-driven rules + **risk-based defaults via trust levels** (read vs write vs destructive). Operator writes explicit rules; trust level supplies the default when no rule matches.

---

## Dexto — Permissions (primary)

**Source:** [Dexto — Permissions Configuration](https://docs.dexto.ai/docs/guides/configuring-dexto/permissions)

- `mode: manual | auto-approve`; `timeout`; `allowedToolsStorage: storage | memory`; `toolPolicies.alwaysAllow`.
- **Resolution order**: session-specific remembered approvals → static `alwaysAllow` policies → dynamic provider → manual/auto-approve mode.
- Tool name format for MCP: `mcp--<server_name>--<tool_name>` (namespaced by server).
- Best practices: "Allow read-only tools — let safe operations run without repeated confirmation"; "Use memory storage for sensitive environments."

**Pattern:** operator-driven config with a clear resolution order; read-only tools get allow-listed. Namespacing tools by server/plugin is a useful convention.

---

## Spring AI Playground — Human-in-the-loop (primary)

**Source:** [spring-ai-playground — human-in-the-loop.md](https://github.com/spring-ai-community/spring-ai-playground/blob/main/docs/features/human-in-the-loop.md)

- Per-tool approval mode: **Required** (ask every run) / **Disabled** (no prompt).
- **Risk-based defaults**: "The mode **defaults to Required above `L0`** and to Disabled at `L0` — the more capable a tool, the more it asks out of the box."
- **Operator override with guardrail**: moving a tool from Required to Disabled opens a "Reduce human oversight?" confirmation — you can't lower the gate by accident.
- Good-defaults guidance: "Keep **Required** for anything that writes, deletes, sends, or spends... Leave **read-only, local tools Disabled** so routine calls don't nag you."
- Fail-safe: no answer within two minutes → declined automatically.

**Pattern:** tool-declared mode + risk-based default + operator override (with a confirmation guardrail on loosening). This is the closest match to the recommended design.

---

## Home Assistant — Permissions (primary)

**Source:** [HA Developer Docs — Permissions](https://developers.home-assistant.io/docs/auth_permissions/), [HA architecture #67 — Permissions](https://github.com/home-assistant/architecture/issues/67)

- Permissions attach to **groups**; the owner always has everything. Policies are dicts; `True` grants, `None` = default deny.
- Merge rule: any `True` wins; dicts recurse; all `None` → `None`.
- Deny-by-default; write implies read.
- HA is **multi-user** (per-user/group policies), which is a different problem than a single-user MCP server. The relevant takeaway is the **deny-by-default + explicit grant** philosophy and the **merge semantics** (most-permissive wins across sources).

---

## Synthesis: how much control to give the user

| Question | Answer from sources |
|---|---|
| Who sets the default policy? | **The plugin/tool author** (OpenAI, Promptise, Spring AI). The author knows which tools are sensitive. |
| What does the user configure? | A thin layer: **global enable switch + per-tool/per-plugin overrides** (OpenAI `always_approve`, Spring AI per-tool toggle, HookWatch rules). |
| Can the user loosen? | Yes, but with a **guardrail** (Spring AI's "Reduce human oversight?" confirmation) and **fail-closed** semantics so loosening is explicit. |
| Can the user tighten? | Yes — override a plugin's safe default to require approval (OpenAI `needs_approval`, HookWatch rules). |
| What if a declared-sensitive tool isn't enforced? | **Refuse to build/run** (Promptise) — never silently allow. |
| What on timeout? | **Deny by default** (Promptise, Spring AI). |
| What are good defaults? | **Risk-based**: read-only → allow; write/send/delete/spend → require (HookWatch trust levels, Spring AI). |

**Bottom line:** give the user **override control, not authoring burden**. The plugin supplies the policy and good defaults; the user gets a global switch and per-tool/per-plugin overrides in both directions, with fail-closed enforcement so a declared-sensitive tool can never silently run.

---

## Sources

1. [MCP spec — Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
2. [MCP spec — Authorization](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization)
3. [SEP-1880: Tool-level scope requirements for MCP tools](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1880)
4. [OpenAI Agents SDK — Human-in-the-loop](https://openai.github.io/openai-agents-python/human_in_the_loop/)
5. [Promptise Foundry — Approval Gates](https://docs.promptise.com/mcp/server/approval-gates/)
6. [HookWatch — MCP Approvals](https://docs.hookwatch.dev/mcp-proxy/approvals)
7. [Dexto — Permissions Configuration](https://docs.dexto.ai/docs/guides/configuring-dexto/permissions)
8. [spring-ai-playground — human-in-the-loop.md](https://github.com/spring-ai-community/spring-ai-playground/blob/main/docs/features/human-in-the-loop.md)
9. [Home Assistant Developer Docs — Permissions](https://developers.home-assistant.io/docs/auth_permissions/)
10. [Home Assistant architecture #67 — Permissions](https://github.com/home-assistant/architecture/issues/67)
