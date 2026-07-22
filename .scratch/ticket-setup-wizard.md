---
title: Create interactive setup wizard
status: open
labels: [wayfinder:ux]
parent: .scratch/portcullis-hardening-map.md
blocked_by: []
---

## Question

What should the `portcullis setup` interactive wizard look like to generate .env files from prompts?

## Resolution Notes

**Decision:**
- New CLI command: `portcullis setup`
- Interactive prompts for each plugin's required secrets
- Support both JSON and line-based whitelist syntax
- Generate .env file with proper formatting
- Validate inputs before writing

**Implementation approach:**
1. Add typer prompts to cli.py
2. Discover plugins and their required env vars via hook
3. Prompt user for each value with helpful descriptions
4. Write .env file with proper escaping
5. Support --output flag to specify path

## Next Step

Design the wizard flow and implement the CLI command. Start by adding a hook for plugins to declare their required env vars.
