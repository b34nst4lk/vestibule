---
title: Portcullis 0.1.0 Hardening Map
status: open
labels: [wayfinder:map]
destination: Production-ready Portcullis MCP server published to PyPI as 0.1.0 with hardened security (audit logging, rate limiting, approval workflows), consistent UX, and an example plugin
---

## Destination

Production-ready Portcullis MCP server published to PyPI as 0.1.0 with:
- Hardened security (audit logging with SecretStr masking, per-tool rate limiting, human-in-the-loop approval workflows)
- Consistent UX (setup wizard, improved error messages, plugins.md registry)
- Example plugin (email subset: list_whitelist, add_to_whitelist)
- Refactored transports (shared handlers in common.py)
- Session management (100 concurrent max, 5-minute TTL)

## Notes

- Domain: Python MCP server development
- Key libraries: pluggy, mcp, pydantic, typer, starlette, uvicorn
- Skills needed: code-review, domain-modeling, grilling, prototype
- Publishing: PyPI ASAP as 0.1.0 (server + example plugin)
- Naming: Product is "Portcullis" — ✅ DONE (all Bulwark refs updated)

## Decisions so far

<!-- Closed tickets will be indexed here as they're resolved -->

- [Fix HTTP/SSE session memory leak](.scratch/ticket-session-leak.md) — SessionInfo dataclass, 100 session hard limit, 5-min TTL via background task + lazy cleanup, HTTP 429 on limit
- [Update naming consistency](.scratch/ticket-naming-consistency.md) — All Bulwark → Portcullis, including env var names
- [Refactor transport duplication](.scratch/ticket-transport-refactor.md) — Extracted 6 shared handlers to common.py, both transports delegate
- [Fix README PyPI claims](.scratch/ticket-readme-fixes.md) — v0.1.0 Beta banner, uv sync installation, clarified workspace plugins
- [Create example plugin](.scratch/ticket-example-plugin.md) — portcullis_example with 3 tools, 13 tests, plugin author README
- [Research MCP prompt support](.scratch/research-mcp-prompt-support.md) — Use elicitation (elicitation/create), not prompts; Hermes has full support, Claude Code has bugs
- [Implement audit logging](.scratch/ticket-audit-logging.md) — JSON audit logs to stdout, SecretStr masking, 10 tests
- [Implement per-tool rate limiting](.scratch/ticket-rate-limiting.md) — Token-bucket limiter in rate_limit.py, per-tool TOML limits, default 60/min, wired into shared tool-call handler
- [Set up PyPI publication workflow](.scratch/ticket-pypi-workflow.md) — Repo published to GitHub (b34nst4lk/portcullis); ci.yml + publish.yml (trusted publishing, v* tag/manual dispatch); RELEASING.md documents release process. **Publishes `portcullis` only** — the example plugin is not published; the first email plugin will be published in a later effort.

## Not yet specified

<!-- Fog of war -- decisions we know are coming but can't yet pin down -->

- Publishing the first email plugin (`portcullis-email`) to PyPI — deferred to a later effort; the publish workflow will need to add it as a published package when that effort starts

## Out of scope

<!-- Work ruled beyond this 0.1.0 destination -->

- Hot-reload of plugins at runtime — explicitly out of scope per original architecture
- Building a hosted plugin registry website — plugins.md + CLI is the approach
- Adding new plugin types beyond the email subset example
- System keychain integration for secrets — .env + wizard is the approach for 0.1.0
- Runtime version compatibility checking — rely on pip/uv dependency resolution
- Publishing `portcullis-example` to PyPI — the example plugin stays in the repo and is covered by CI, but is not released; only the `portcullis` server is published

---

## Frontier Tickets

<!-- Child tickets -- link by name, detail lives in the ticket file -->

### Security Features

- ~~[Implement audit logging infrastructure](.scratch/ticket-audit-logging.md) — Structured JSON to stdout, SecretStr masking~~ ✅ DONE
- ~~[Implement per-tool rate limiting](.scratch/ticket-rate-limiting.md) — Token bucket, configurable per-tool limits~~ ✅ DONE
- [Implement approval workflow system](.scratch/ticket-approval-workflow.md) — Global approval_mode with per-tool override, MCP elicitation

### UX Improvements

- [Create interactive setup wizard](.scratch/ticket-setup-wizard.md) — `portcullis setup` generates .env from prompts
- [Improve error message consistency](.scratch/ticket-error-messages.md) — Document hybrid approach, rely on MCP defaults
- [Create plugins.md registry](.scratch/ticket-plugins-registry.md) — Curated markdown for plugin authors to PR

### Publishing Prep

- ~~[Refactor transport duplication](.scratch/ticket-transport-refactor.md) — Extract shared handlers to common.py~~ ✅ DONE
- ~~[Fix HTTP/SSE session memory leak](.scratch/ticket-session-leak.md) — Hard limit (100) + TTL (5 min)~~ ✅ DONE
- ~~[Update naming consistency](.scratch/ticket-naming-consistency.md) — Change Bulwark → Portcullis everywhere~~ ✅ DONE
- ~~[Fix README PyPI claims](.scratch/ticket-readme-fixes.md) — Update installation for 0.1.0 reality~~ ✅ DONE
- ~~[Create example plugin](.scratch/ticket-example-plugin.md) — portcullis_example with whitelist tools only~~ ✅ DONE
- ~~[Implement audit logging infrastructure](.scratch/ticket-audit-logging.md) — JSON audit logs, SecretStr masking~~ ✅ DONE
- ~~[Set up PyPI publication workflow](.scratch/ticket-pypi-workflow.md) — GitHub Actions for build/publish~~ ✅ DONE

---

## Blocking Dependencies

```
┌─────────────────────────────────────────────────────────────────┐
│                    Must Complete First                          │
│  ┌─────────────────┐  ┌─────────────────┐                       │
│  │ 11. Example     │  │ 8. README PyPI  │                       │
│  │     plugin      │  │     fixes       │                       │
│  └────────┬────────┘  └────────┬────────┘                       │
│           │                    │                                 │
│           ▼                    ▼                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              12. PyPI publication workflow               │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    Can Run In Parallel                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ 1. Audit     │  │ 2. Rate      │  │ 3. Approval  │          │
│  │    logging   │  │    limiting  │  │    workflow  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ 4. Setup     │  │ 5. Error     │  │ 6. plugins.md│          │
│  │    wizard    │  │    messages  │  │    registry  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```
