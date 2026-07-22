---
title: Create example plugin for PyPI
status: open
labels: [wayfinder:publishing]
parent: .scratch/portcullis-hardening-map.md
blocked_by:
  - .scratch/ticket-transport-refactor.md
---

## Question

What should the example plugin contain to demonstrate the Portcullis plugin API?

## Resolution Notes

**Decision:**
- Package: portcullis_example
- Location: packages/portcullis_example/
- Tools: list_whitelist (returns static list), add_to_whitelist (runtime only)
- No actual email sending — just whitelist management demo
- Include pyproject.toml with entry point
- Include README with plugin author guide

**Implementation approach:**
1. Create packages/portcullis_example/ directory structure
2. Implement hooks: portcullis_register_plugin_info, portcullis_register_tools
3. Add to uv workspace
4. Write README for plugin authors
5. Test installation and loading

## Next Step

Create the example plugin package based on the email plugin subset. Model it after portcullis_email but simplified.
