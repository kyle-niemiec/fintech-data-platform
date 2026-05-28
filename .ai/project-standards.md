# Project Standards

## Business Story
- `.ai/docs/meridian-lore.md` is the primary business story for Meridian as a firm. Consult it when work needs business context — departments, business lines, regulatory posture, or how internal operations connect.

## Architecture And Scope
- Build only what is currently required; no speculative scaffolding unless explicitly requested.
- Keep service boundaries event-driven and aligned with planning docs.
- Prefer minimal, reversible changes over broad rewrites.

## Data-Handling Expectations
- Pre-launch/demo paths may use synthetic or non-sensitive datasets.
- Production-like handling still applies: least privilege, immutable lineage, explicit provenance, and auditable transitions.
- Never introduce shortcuts that blur demo-only behavior with production-data controls.

## Tech-Debt Discipline
- Track only unresolved debt in `.ai/docs/development/tech-debt.md`; do not keep completed-work history there.
- Every deferred compromise must have both a `TECH-DEBT:` code comment and one matching ledger entry.
- When debt is resolved, remove the `TECH-DEBT:` code comment and matching ledger entry in the same round.

## Readability And Whitespace
- Use descriptive names and small, single-purpose units.
- Use one blank line between logical sections; avoid stacked empty lines.
- No trailing whitespace.
- Keep formatting consistent with surrounding files and existing project conventions.
