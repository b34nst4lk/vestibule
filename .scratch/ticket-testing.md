---
title: Define testing strategy for server and plugins
status: closed
labels: []
parent: .scratch/plugin-mcp-server-map.md
resolved: pytest + pytest-cov + pytest-asyncio; src/ layout; hybrid unit+integration tests; full coverage for server and plugins
---

## Question

How do we test the server and plugins?

## Resolution

### Decision Summary

| Aspect | Decision |
|--------|----------|
| **Test framework** | pytest + `pytest-cov` + `pytest-asyncio` + `pytester`-style isolation |
| **Test layout** | `src/` layout with separate `tests/` directory |
| **Plugin isolation** | Hybrid: unit tests for hook logic + integration tests for plugin loading |
| **Server coverage** | Full coverage: plugin discovery, hooks, config, secrets, transports |
| **Plugin coverage** | Full behavior: hooks, handlers, config validation, secrets, errors |

### Test Structure

```
portcullis/
  packages/
    portcullis/
      src/portcullis/
        __init__.py
        hooks.py
        plugin_manager.py
      tests/
        conftest.py
        test_hooks.py
        test_plugin_manager.py
        test_config.py
        test_transports/
          test_stdio.py
          test_http_sse.py
    portcullis-email/
      src/portcullis_email/
        __init__.py
      tests/
        conftest.py
        test_email_plugin.py
        test_handlers.py
```

### Dev Dependencies

```toml
# packages/portcullis/pyproject.toml
[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.0",
    "pytest-asyncio>=0.23",
    "httpx",
]
```

### Example Test Patterns

```python
# Unit test: hook logic
def test_register_tools_hook():
    registry = ToolRegistry()
    portcullis_email.portcullis_register_tools(registry)
    assert len(registry.tools) > 0

# Integration test: plugin loads correctly
def test_email_plugin_integration(pytester):
    result = pytester.runpytest_subprocess("--portcullis-plugin=portcullis-email")
    result.assert_outcomes(passed=1)

# Handler test: with valid input
async def test_send_email_handler():
    result = await send_email_handler(
        SendEmailRequest(recipient_name="Alice", subject="Test", body="Hello")
    )
    assert "sent" in result.lower()
```
