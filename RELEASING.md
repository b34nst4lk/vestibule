# Releasing Vestibule

This document describes how to publish a new version of Vestibule to PyPI.

## Overview

Releases are automated via GitHub Actions. Two workflows live in
`.github/workflows/`:

- **`ci.yml`** — runs on every push/PR to `main`: lint (ruff), tests (pytest),
  and builds both packages. This is the safety gate before any release.
- **`publish.yml`** — builds `vestibule` and publishes it to PyPI. Triggered
  by pushing a `v*` tag **or** manually via the Actions tab ("Run workflow").

> **Scope:** Only the `vestibule` server package is published to PyPI. The
> example plugin (`vestibule-example`) is built and tested in CI but is **not**
> published. The first email plugin will be published in a later effort.

## One-time setup: PyPI trusted publishing

The publish workflow uses **trusted publishing (OIDC)** — no API token is
stored in the repo. Before the first release, configure each PyPI project to
trust this GitHub repository:

1. Go to the PyPI project's **"Publishing"** settings
   (https://pypi.org/manage/project/<name>/publishing/).
2. Add a **pending publisher** with:
   - **Workflow**: `publish.yml`
   - **Environment**: *(leave blank)*
   - **Repository owner**: `b34nst4lk`
   - **Repository**: `vestibule`
3. Configure this for the `vestibule` project only. (The example plugin is
   not published; the email plugin will be added when it is released later.)

Once the first release succeeds, the pending publishers become active.

## Cutting a release

1. **Bump the version** in `pyproject.toml` (root).
2. **Update `uv.lock`**: `uv lock`.
3. **Commit** the version bump and push to `main`. Confirm `ci.yml` passes.
4. **Tag the release** and push the tag:

   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

   Pushing the tag triggers `publish.yml`, which builds and publishes
   `vestibule` to PyPI.

5. **Verify** the release on PyPI and that the GitHub Actions run succeeded.

## Manual release (no tag)

If you need to publish without a tag, go to the **Actions** tab → **Publish to
PyPI** → **Run workflow**. This builds and publishes the current `main` HEAD.

## Notes

- Only the `vestibule` server package is published. The example plugin stays
  in the repo and is covered by CI, but is not released to PyPI.
- The `dist/` directory is gitignored; artifacts are produced fresh by CI.
- If a version already exists on PyPI, the publish step fails (`skip_existing`
  is off) — bump the version before re-releasing.
