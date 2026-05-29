# Project Standards

## Business Story
- `.ai/docs/meridian-lore.md` is the primary business story for Meridian as a firm. Consult it when work needs business context: departments, business lines, regulatory posture, or how internal operations connect.

## Corporate Voice
The canonical voice for describing Meridian as a firm. Used for business stories, business architecture descriptions, departmental walkthroughs, and any external-facing copy that introduces what the firm does or how it operates.

### Use for
- `.ai/docs/meridian-lore.md`
- UI business stories (`apps/ui/src/lib/businessStories.tsx`, `apps/ui/src/pages/HomePage.tsx`)
- The README's "Welcome to Meridian" framing
- Any future external-facing copy that introduces Meridian

### Do not use for
- Technical operations or runbook material
- CI/CD or deployment narration
- Author or developer commentary
- Agent-facing internal docs
- Testing material

### Style rules
- First-person plural ("we execute trades for client accounts") or close third ("Meridian ingests three very different sources"). No academic third person.
- Bold the first introduction of a department name, product line, or term of art. Italicize formulas or quoted values sparingly.
- Punctuation balance: em-dashes only for true mid-sentence breaks the sentence cannot do without; colons for directly relevant follow-on clauses; semi-colons for related-but-distinct clauses. A well-written paragraph uses all three in measured proportion, not em-dashes alone.
- Each paragraph should answer one question: what is this, who owns it, why it matters, or how it connects.
- Technical terms get a one-sentence business gloss before being used.
- Aphoristic section titles where they fit ("Every record has to be accountable."); standard headings are fine when they don't.
- Visual aids are used tastefully and selectively. Tables, diagrams, and figures break the flow of business prose when stacked. A page generally tolerates one well-placed visual aid; two only when each genuinely earns its space. Repeated or reused visual aids across surfaces are a smell: link to the canonical version instead.

## Author Style (Kyle)
Personal punctuation balance for first-person author commentary: README personal notes, the AI-assistance paragraph, "Where to learn more" framing, and similar author-voice sections. Distinct from corporate voice, which is about Meridian.

- Em-dashes are used sparingly — kept for genuine mid-sentence breaks (the kind that need em-dashes if you know what I mean), not as a default parenthetical.
- Colons (`:`) introduce directly relevant follow-on: a definition, an enumeration, the thing the sentence is actually about.
- Semi-colons (`;`) join related-but-independent clauses; they make a sentence feel composed rather than chained.
- A balanced paragraph uses all three. Em-dashes-only is a style tell, and not the right one.

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
