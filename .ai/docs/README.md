# AI Docs Map

## Documentation Split
- `planning/`: source-of-truth for product intent and specification direction.
- `development/`: source-of-truth for active implementation status and work-in-progress tracking.

## Authority Rules
- Product decisions, architecture constraints, and requirement intent come from `planning/`.
- Current implementation deltas, temporary deviations, and execution notes live in `development/`.
- If implementation temporarily differs from plan, capture the gap in development docs and `development/tech-debt.md`.
