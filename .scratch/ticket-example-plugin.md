---
title: Create example plugin for PyPI
status: closed
labels: [wayfinder:publishing]
parent: .scratch/portcullis-hardening-map.md
blocked_by:
  - .scratch/ticket-transport-refactor.md
resolved: Created portcullis_example package with list_whitelist, add_to_whitelist, remove_from_whitelist tools. In-memory whitelist (no persistence). Includes 13 tests, all passing.
---

## Question

What should the example plugin contain to demonstrate the Portcullis plugin API?

## Resolution Notes

**Created:**
- `packages/portcullis_example/portcullis_example/__init__.py` - Plugin implementation
- `packages/portcullis_example/pyproject.toml` - Package config with entry point
- `packages/portcullis_example/README.md` - Plugin author guide
- `packages/portcullis_example/tests/test_example_plugin.py` - 13 tests

**Tools:**
- `list_whitelist()` - List all whitelisted recipients
- `add_to_whitelist(name, email)` - Add to runtime whitelist
- `remove_from_whitelist(name)` - Remove from runtime whitelist

**Features:**
- Demonstrates all required hooks (plugin_info, config_schema, init, register_tools)
- In-memory whitelist (no persistence) - simple demo
- Configurable initial_whitelist via TOML config
- 13 tests, all passing (79 total in suite)

**Files changed:**
- Created `packages/portcullis_example/` directory
- Updated `pyproject.toml` - Added workspace member + testpaths
- Updated `README.md` - Added example plugin section

## Next Step

Example plugin ready for PyPI publication. Next: Create plugins.md registry or PyPI workflow.
