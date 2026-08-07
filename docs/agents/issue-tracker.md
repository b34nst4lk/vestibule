# Issue Tracker — GitHub Issues

This repo tracks **open** issues as GitHub issues on
[`b34nst4lk/vestibule`](https://github.com/b34nst4lk/vestibule/issues).

## Open tickets

Open tickets (including wayfinder maps and their child tickets) live as GitHub
issues. They use the `wayfinder:*` labels (`wayfinder:map`, `wayfinder:security`,
`wayfinder:ux`, `wayfinder:publishing`, `wayfinder:code-quality`,
`wayfinder:research`).

### Parent/child relationships

GitHub sub-issues are not enabled for this repo, so the parent relationship
uses a **body convention**: each child ticket's body begins with a `> **Parent:**`
line linking to its map issue.

### Blocking/dependencies

GitHub sub-issues (native blocking) are not available. Use the body convention:
reference the blocking issue by link in the ticket body.

## Closed decision records

Closed tickets are retained as markdown files under `.scratch/` as a local
record of decisions made. They are not duplicated on GitHub.

## Resolving an issue

To close a GitHub issue:
1. Post the resolution as a comment on the issue.
2. Close the issue.
3. Append a context pointer to the map's **Decisions so far** section.
