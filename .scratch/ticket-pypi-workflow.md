---
title: Set up PyPI publication workflow
status: open
labels: [wayfinder:publishing]
parent: .scratch/portcullis-hardening-map.md
blocked_by:
  - .scratch/ticket-naming-consistency.md
  - .scratch/ticket-readme-fixes.md
  - .scratch/ticket-example-plugin.md
---

## Question

How should PyPI publication be automated for Portcullis 0.1.0?

## Resolution Notes

**Decision:**
- GitHub Actions workflow for building and publishing
- Trigger: manual dispatch + tag push
- Build both portcullis and portcullis_example wheels
- Publish to PyPI using API token secret
- Include README, LICENSE, classifiers

**Implementation approach:**
1. Create .github/workflows/publish.yml
2. Configure PyPI API token as repository secret
3. Build sdist and wheel for both packages
4. Test with TestPyPI first
5. Document release process

## Next Step

Create the GitHub Actions workflow and test with TestPyPI. Document the release process for future publishes.
