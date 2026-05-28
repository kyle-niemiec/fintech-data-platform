# Development Loop

Use this loop for every task:

1. Load context in the required bootstrap order and any relevant agent skills (e.g. Superpowers).
2. Align the task with planning docs in `.ai/docs/planning/`. Once all project planning is completed, align the task with known project standards.
3. Implement the minimal change that satisfies the requirement.
4. Verify with targeted checks/tests for impacted behavior.
5. Reconcile tech debt tracking: every `TECH-DEBT:` code tag must map to one `.ai/docs/development/tech-debt.md` entry, and every ledger entry must map to an existing `TECH-DEBT:` code tag.
6. Update development tracking docs, including `.ai/docs/development/roadmap.md` and `.ai/docs/development/tech-debt.md`.
7. Report what changed, what remains, and explicit risks/deltas versus plan. The explanation should sufficiently answer the questions "What was the problem" and "How does this solution help fix the problem".
