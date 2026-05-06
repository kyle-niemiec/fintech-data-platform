# Development Docs

`development/` tracks active implementation reality, not long-term product intent.

## Structure
- State is organized by development area, not by dated activity logs.
- Each file should capture durable current-state facts for its area.
- Exclude non-state process metadata (date-based log framing, command transcripts, plan-alignment notes, and follow-up process reminders).

## Current Development Areas
- `orchestration.md`
- `runtime-integrations.md`
- `code-modularity.md`
- `quality-assurance.md`
- `tech-debt.md`

## Update Expectations
- Update relevant development-area files every implementation round.
- Keep `tech-debt.md` as an outstanding-only list of unresolved implementation debt.
- Every unresolved debt item must have one matching `TECH-DEBT:` code comment and one matching ledger entry.
- When adding/removing `TECH-DEBT:` code comments, add/remove the corresponding `tech-debt.md` entry in the same round.
