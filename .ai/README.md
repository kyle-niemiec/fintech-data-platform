# AI Context Root

## Project Overview
Fintech Data Platform is an event-driven, compliance-aligned data engineering project with infrastructure-as-code and read-only UI/API surfaces.

## What Lives Here
- `.ai/README.md`: root context map and conflict-precedence rules.
- `.ai/project-standards.md`: coding, architecture, and readability standards.
- `.ai/development-loop.md`: required implementation and review loop per task.
- `.ai/session-prompt.md`: reusable prompt that loads project context in order.
- `.ai/docs/`: domain docs split by planning intent vs development execution tracking.

## Context Loading Rules
- Start from `AGENTS.md` (or `CLAUDE.md`) and follow the required load order exactly.
- `planning/` docs are authoritative for product intent, architecture direction, and scoped behavior.
- `development/` docs are authoritative for current implementation status, deltas, and debt tracking.
- If planning and development diverge, implement to planning intent and document any temporary gap in development docs and `tech-debt.md`.
