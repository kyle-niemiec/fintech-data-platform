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
- Keep `tech-debt.md` in sync with code comments (`TODO`, `FIXME`, temporary guards, deferred cleanup notes).
- When adding/removing debt-related comments in code, add/update/resolve the corresponding `tech-debt.md` entry in the same round.
