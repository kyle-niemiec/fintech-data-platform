# Tech Debt

Track only unresolved implementation debt: deferred compromises, temporary guards, and placeholder behavior that still needs follow-up work.

## Rules
- Keep this file outstanding-only; do not store completed work history here.
- Every row must map to exactly one unresolved `TECH-DEBT:` code comment.
- Every unresolved `TECH-DEBT:` code comment must have exactly one row in this file.
- When debt is resolved, remove both the `TECH-DEBT:` code comment and the matching row in the same round.

## Outstanding Items

| Area | Debt | TECH-DEBT Tag Location | Exit Criteria |
| --- | --- | --- | --- |
| CDC / fraud worker | Inline SQL literals in the handler instead of externalized SQL resources | `services/workers/fraud_worker/handler.py:123` | risk_flag/assessed SQL is moved out of Python into package SQL resources |
| CDC / fraud worker | Oversized handler method doing row extraction, scoring, upsert, and emit | `services/workers/fraud_worker/handler.py:178` | method is split into smaller single-purpose functions |
| Worker bootstrap | Duplicated platform-service construction needs factory consolidation | `services/workers/fraud_worker/main.py:36` | shared factory consolidates service construction |
| Worker bootstrap | Duplicated platform-service construction needs factory consolidation | `services/workers/salesforce_bronze_writer/main.py:33` | shared factory consolidates service construction |
| OLTP load generator | Inline SQL literals should be consolidated outside Python code | `services/workers/oltp_load_generator/main.py:34` | generator SQL is externalized from Python |
| OLTP load generator | Duplicated platform-service construction needs factory consolidation | `services/workers/oltp_load_generator/main.py:116` | shared factory consolidates service construction |
