---
title: Set up PyPI publication workflow
status: closed
labels: [wayfinder:publishing]
parent: .scratch/portcullis-hardening-map.md
blocked_by:
  - .scratch/ticket-naming-consistency.md
  - .scratch/ticket-readme-fixes.md
  - .scratch/ticket-example-plugin.md
resolved: Repo published to GitHub (b34nst4lk/portcullis); CI + publish workflows added and verified; release process documented in RELEASING.md
---

## Question

How should PyPI publication be automated for Portcullis 0.1.0?

## Resolution Notes

**Decision:**
- GitHub Actions workflow for building and publishing
- Trigger: manual dispatch + tag push
- Build both portcullis and portcullis_example wheels
- Publish to PyPI using trusted publishing (OIDC) — no stored API token
- Include README, LICENSE, classifiers

**Implemented:**
- Repo created and pushed to GitHub: `b34nst4lk/portcullis` (public)
- `.github/workflows/ci.yml` — lint (ruff), test (pytest), build both packages on every push/PR to main
- `.github/workflows/publish.yml` — build both packages + publish to PyPI via trusted publishing, triggered on `v*` tag push or manual dispatch
- `RELEASING.md` — documents the release process and one-time PyPI trusted-publisher setup

**Verified:**
- CI run green (lint, test, build)
- Publish workflow triggered via manual dispatch; both packages build successfully; publish step reaches PyPI and only fails because trusted publishing is not yet configured on the PyPI project (expected — see RELEASING.md)

**Next Step**

None — resolved. Remaining external step: configure PyPI trusted publishing for `portcullis` and `portcullis-example` (documented in RELEASING.md).
