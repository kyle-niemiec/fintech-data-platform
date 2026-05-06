# Agent Bootstrap

Purpose: bootstrap AI sessions with a consistent, operational context-loading flow.

## Required Load Order
1. `.ai/README.md`
2. `.ai/project-standards.md`
3. `.ai/development-loop.md`
4. `.ai/docs/README.md`
5. `.ai/docs/planning/README.md`
6. `.ai/docs/development/README.md`

## Operating Rules
- Before coding, read around the current prompt and inspect adjacent code/docs in the impacted area.
- Reconcile implementation choices with planning source-of-truth docs in `.ai/docs/planning/`.
- Treat `.ai/docs/development/` as active tracking and update it every work round.
- Update `.ai/docs/development/tech-debt.md` for every deferred compromise, temporary workaround, or resolved debt item.
- If docs conflict: planning docs define product intent; development docs define current execution status. Record reconciliation decisions in development docs.
