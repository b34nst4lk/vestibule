# Issue Tracker — Local Markdown

This repo tracks issues as markdown files under `.scratch/`.

## Creating issues

Issues are markdown files with a frontmatter header containing at minimum:
- `title`: The issue title
- `status`: One of `open`, `closed`
- `labels`: (optional) List of triage labels

Example:
```markdown
---
title: Add user authentication
status: open
labels: [needs-triage]
---

Issue description goes here.
```

## Referencing issues

Issues are referenced by their file path within `.scratch/`, e.g. `.scratch/auth/login-flow.md`.

## Blocking/dependencies

Use a `blocked_by:` field in frontmatter to list dependencies:
```markdown
blocked_by:
  - .scratch/auth/user-model.md
```

## Resolving issues

To close an issue:
1. Change `status: open` to `status: closed` in frontmatter
2. Add a `resolved:` field with a brief summary of the resolution
