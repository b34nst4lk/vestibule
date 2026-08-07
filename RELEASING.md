# Releasing Portcullis

This document describes how to publish a new version of Portcullis to PyPI.

## Overview

Releases are automated via GitHub Actions. Two workflows live in
`.github/workflows/`:

- **`ci.yml`** — runs on every push/PR to `main`: lint (ruff), tests (pytest),
  and builds both packages. This is the safety gate before any release.
- **`publish.yml`** — builds `portcullis` and `portcullis-example` and publishes
  them to PyPI. Triggered by pushing a `v*` tag **or** manually via the
  Actions tab ("Run workflow").

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
   - **Repository**: `portcullis`
3. Repeat for both `portcullis` and `portcullis-example`.

Once the first release succeeds, the pending publishers become active.

## Cutting a release

1. **Bump the version** in `pyproject.toml` (root) and
   `packages/portcullis_example/pyproject.toml` (and
   `packages/portcullis_email/pyproject.toml` if it is released too).
2. **Update `uv.lock`**: `uv lock`.
3. **Commit** the version bump and push to `main`. Confirm `ci.yml` passes.
4. **Tag the release** and push the tag:

   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

   Pushing the tag triggers `publish.yml`, which builds and publishes both
   packages to PyPI.

5. **Verify** the release on PyPI and that the GitHub Actions run succeeded.

## Manual release (no tag)

If you need to publish without a tag, go to the **Actions** tab → **Publish to
PyPI** → **Run workflow**. This builds and publishes the current `main` HEAD.

## Notes

- Both packages are always built and published together so the example plugin
  stays in sync with the server.
- The `dist/` directory is gitignored; artifacts are produced fresh by CI.
- If a version already exists on PyPI, the publish step fails (`skip_existing`
  is off) — bump the version before re-releasing.
