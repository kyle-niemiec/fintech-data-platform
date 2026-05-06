# Development Docs

`development/` tracks active implementation reality, not long-term product intent.

## Use These Docs For
- Current task status, execution deltas, and known gaps.
- Temporary workarounds, sequencing notes, and cleanup commitments.
- Debt tracking through `tech-debt.md`.

## Update Expectations
- Update development docs every implementation round.
- Keep `tech-debt.md` in sync with code comments (`TODO`, `FIXME`, temporary guards, deferred cleanup notes).
- When adding/removing debt-related comments in code, add/update/resolve the corresponding `tech-debt.md` entry in the same round.
