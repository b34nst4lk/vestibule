---
title: Plugin-based MCP Server - Wayfinder Map
status: open
labels: [wayfinder:map]
destination: Build a plugin-based MCP server using pluggy (pytest-style hooks) where plugins are discovered via entry points, configured in TOML, secrets from .env/env vars, serving MCP tools over both stdio and HTTP/SSE transports, loaded at startup. Primary use case: custom skills that hide sensitive info from agents (e.g., email whitelisting).
---

## Destination

Build a plugin-based MCP server using `pluggy` where:
- Plugins are discovered via entry points and configured in a TOML file
- Secrets are loaded from `.env`/environment variables
- MCP tools are exposed over **both stdio and HTTP/SSE** transports
- Plugins are loaded at startup (no hot-reload or runtime management)
- Primary use case: custom skills that hide sensitive information from agents — e.g., a tool that sends emails/invites only to whitelisted recipients

## Notes

- Domain: Python MCP server development
- Key library: `pluggy` for plugin architecture
- Skills needed: MCP protocol knowledge, plugin architecture design, HTTP/SSE and stdio transport implementation

## Decisions so far

<!-- Index of closed tickets — populated as tickets are resolved -->

- [Select MCP library or implementation approach](.scratch/ticket-mcp-library.md) — Use official `mcp` package from Anthropic
- [Define secrets management approach](.scratch/ticket-secrets.md) — Plugin-declared env_prefix with collision detection; `portcullis healthcheck` command
- [Define TOML configuration schema](.scratch/ticket-config-schema.md) — Multi-level config (CLI > project > user); plugin-declared Pydantic models; fail-fast validation
- [Define pluggy hook specs for the server](.scratch/ticket-hook-specs.md) — 5 hook specs created; PluginManager implemented; 18 tests passing
- [Define plugin package structure and entry point](.scratch/ticket-plugin-structure.md) — Entry point `portcullis.plugins`; package `portcullis-<name>`; hooks in `__init__.py`; all hooks optional
- [Define deployment and installation approach](.scratch/ticket-deployment.md) — PyPI for users, source for dev; `portcullis` CLI with subcommands; uv workspace
- [Define testing strategy for server and plugins](.scratch/ticket-testing.md) — pytest + pytest-cov + pytest-asyncio; src/ layout; hybrid unit+integration tests

## Not yet specified

<!-- Fog of war -- decisions we know are coming but can't yet pin down -->

*(All initial decisions have been ticketed — fog cleared as we advance)*

## Out of scope

<!-- Work ruled beyond this destination -->

- Hot-reload of plugins at runtime
- Enable/disable plugins at runtime
- Version compatibility checking between server and plugins
