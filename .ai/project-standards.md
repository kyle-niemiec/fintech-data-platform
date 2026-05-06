# Project Standards

## Architecture And Scope
- Build only what is currently required; no speculative scaffolding unless explicitly requested.
- Keep service boundaries event-driven and aligned with planning docs.
- Prefer minimal, reversible changes over broad rewrites.

## Data-Handling Expectations
- Pre-launch/demo paths may use synthetic or non-sensitive datasets.
- Production-like handling still applies: least privilege, immutable lineage, explicit provenance, and auditable transitions.
- Never introduce shortcuts that blur demo-only behavior with production-data controls.

## Tech-Debt Discipline
- Every deferred compromise must be logged in `.ai/docs/development/tech-debt.md`.
- Every resolved debt item must be marked resolved/removed in the same round it is fixed.
- Debt notes in code and debt ledger entries must stay synchronized.

## Readability And Whitespace
- Use descriptive names and small, single-purpose units.
- Use one blank line between logical sections; avoid stacked empty lines.
- No trailing whitespace.
- Keep formatting consistent with surrounding files and existing project conventions.
