# Reusable Session Prompt

Use this prompt to start a new AI session:

```text
Load project context in this exact order before proposing or changing code:
1) .ai/README.md
2) .ai/project-standards.md
3) .ai/development-loop.md
4) .ai/docs/README.md
5) .ai/docs/planning/README.md
6) .ai/docs/development/README.md

Then read the current task prompt and inspect nearby code/docs for the impacted area.
Treat .ai/docs/planning/ as source-of-truth for product intent.
Treat .ai/docs/development/ as source-of-truth for active implementation tracking.
Before development-doc updates, reconcile `TECH-DEBT:` code tags with .ai/docs/development/tech-debt.md entries.
Update development tracking docs every round, especially .ai/docs/development/tech-debt.md (outstanding items only).
Implement minimal changes, verify results, and report deltas and risks.
```
