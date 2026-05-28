# Meridian: The Firm Behind the Platform

A portrait of Meridian as an entity — who the firm is, what it does, who works inside it, and the regulatory frame that shapes every decision. The platform that connects it all is documented in detail under [`planning/`](planning/); this file is about the company those pipelines exist to serve.

## Meridian at a glance

**Meridian Wealth Management** is a mid-sized wealth-management firm. We manage portfolios for individual and household clients, execute trades against their accounts, extend credit against those portfolios, and pay our advisors on the relationships they build. We are a fictional firm — built to model, faithfully, the data-engineering problem a regulated financial firm actually faces — but every business line, department, and control described in this document is one the platform was built to support. Nothing in this portrait is decoration.

Our regulatory frame is anchored in **FINRA** and **SOC 2**, with **GDPR**-style data-subject handling as a deliberate stretch objective. We are not certified to any of those frameworks; we are *aligned* to them by architecture and operating practice. The entire data discipline at Meridian — the immutable audit trail, the lawful retention windows, the byte-by-byte accountability we ask of every record — flows from one premise: every number we can show leadership has to be a number we can defend in front of a regulator.

## What Meridian does

We run four interlocking business lines. They share clients, they share advisors, and they share a single accounting of truth — but each one produces data in a different shape, on a different schedule, from a different system.

### The Trading Desk and client advisors

The **Trading Desk** is Meridian's front office. Together with our client-facing **advisors**, the desk executes orders against client **accounts**, with some flowing in directly from a client-facing app. Every order is written into our transactions database — the firm's system of record for activity in client portfolios. The instrument universe runs the names you would expect on a mid-sized desk: large-cap equities like AAPL, MSFT, GOOG, AMZN, NVDA, TSLA, JPM, and BAC.

Real-time risk and fraud scoring sits beside the desk, not behind it. A single mis-booked or fraudulent trade can move real money and trigger regulatory scrutiny, so every order is scored the moment it lands rather than overnight. The model is continuous and per-instrument — a smooth curve, *r(x) = 1 − r_f / (x + r_f)*, calibrated for each ticker so that an unremarkable $10,000 trade in AAPL and an alarming $1,000 trade in NVDA land at the same risk level. Anything scoring 0.9 or above raises a high-severity alert and pulls **Risk & Compliance** into the loop.

### The lending book

Alongside the trading book we keep a **lending book** — credit extended to clients against the assets we hold for them. Each loan is tracked with its current principal balance, the original amount disbursed, a status code (`current`, `delinquent`, or `paid_off`), days past due, and a scheduled payment cadence. Every transition from one status to the next is captured as a separate event in an immutable **loan status history**, so an auditor can reconstruct exactly what state any loan was in at any moment in its life.

Payments themselves are tracked separately. Each payment carries the loan it belongs to, the dollar amount, its currency, the date it was scheduled to land, and the date it actually posted — which lets us measure not just whether borrowers are paying, but whether they are paying *on time*.

### The advisor network and commission program

Our advisors are compensated through commissions, and commissions are not always tidy. **Revenue Operations** runs an adjustment program that captures the corrections that have to happen after a normal pay cycle — a **retro credit** for a deal whose attribution was missed, a **chargeback** when a commission needs to be clawed back, or a **manual override** when none of the standing rules quite fit. Each adjustment carries the advisor it applies to, the effective date, the dollar amount, the reason, and a currency. RevOps loads these once per cycle as a workbook into the platform's governed on-ramp.

### The client relationship and sales pipeline

**Sales** owns the client relationship layer. We use Salesforce as our system of record for client **accounts** and the **opportunities** that move them from prospect to client — household onboarding, additional asset transfers, new lending applications. The CRM is pulled into the platform on incremental, scheduled batches so the rest of the firm — Trading, Finance, BI — sees a single, current picture of who our clients are without anyone outside Sales needing direct CRM access.

## The people inside Meridian

A firm is its departments. Here is who lives where, what they own, and how they hand off to the next team.

The **Trading Desk** is the floor. Orders happen here, and their database is the system of record for every trade Meridian executes.

**Client Advisors** sit between the desk and the household. They place orders on behalf of clients, own the relationship, and earn the commission — which means every advisor appearing in a RevOps adjustment is a person whose paycheck we are about to change.

**People Operations** runs payroll. Each pay cycle, People Ops produces a payroll workbook — one row per employee with employee ID, pay-period end date, gross and net pay, and currency — and uploads it to the platform's governed on-ramp. People Ops is one of two teams in the firm that still runs core processes in Excel; the other is Revenue Operations.

**Revenue Operations** owns advisor compensation. They reconcile the commission adjustments described above into a workbook each cycle and upload it through the same on-ramp People Ops uses. When something goes wrong with a load — the wrong currency code, a missing column — RevOps is the team that has to correct the file and resubmit. In some workflows the same team is also referred to as **Compensation Operations**.

The recurring uploaders behind People Ops and RevOps are real identities the platform seeds by name: **James Beringer**, **Kathy Winston**, and **Alex Ortiz**. They are the human beings whose names sit behind every Excel run in the audit trail.

**Sales** maintains the CRM. They are the source of truth for who our clients are and where each one sits in the journey from prospect to fully-onboarded household.

**Risk & Compliance** is the firm's first line of defense. They watch the alerts feed — every quarantined upload, every high-risk trade, every pipeline failure — and triage from there. A rejected financial load is itself an auditable event for them, even before anyone investigates *why* it rejected, because regulators expect us to know our own data movements.

The **Financial Crime Unit** takes over when Risk & Compliance identifies a pattern that looks like more than a one-off — a string of trades whose timing and sizing match an evasion playbook, or activity around a client that doesn't reconcile with what Sales knows about them. The FCU opens formal cases, and where the law requires it, files reports with the relevant regulator. This is the path a confirmed high-severity fraud flag travels.

**Data Platform / SRE** is the connective-tissue team. They operate the pipelines, restart workers when lag climbs, scale consumers when a partition falls behind, and run backfills at the request of Finance or Risk & Compliance. When the desk says something looks off, SRE is the first phone call.

**BI & Leadership** consume the firm's headline numbers. Four KPIs sit above the rest: **pipeline conversion** (how the Sales book is moving), **portfolio health** (how the lending book is performing), **payment performance** (how on-time our borrowers are), and **commission economics** (where advisor pay is going). Leadership never touches raw data; the firm has agreed that the gold tier is the only surface from which an executive reads Meridian's numbers.

**Data Science & Analysts** sit between leadership and the underlying record. They work with cleaned, normalized, PII-tokenized data — building features, producing regulatory reports, and answering the questions that the headline KPIs alone cannot. They are the firm's interpreters.

## The regulatory frame

Three regulatory regimes shape how we operate.

**FINRA** governs the books-and-records side of our trading and lending. Trade records have to be defensible, retained for the relevant window — typically seven years — and reproducible on request. Our immutable record-of-truth tier exists primarily because of this rule: it is the firm's legal record, and nothing else in the platform is allowed to mutate it.

**SOC 2** governs how we run as a service-providing organization — controls around access, change management, monitoring, and the audit trail those controls produce. The least-privilege identity model under which every worker, every analyst, and every executive surface in the platform operates is the operational manifestation of our SOC 2 posture.

**GDPR** is, strictly, beyond our reach today, but we treat it as a stretch objective because the discipline it forces is the same discipline our other regimes will eventually demand of us. The hard part is honoring a client's right to be forgotten without breaching a seven-year retention obligation — and we solve it by crypto-shredding the per-subject key that ties a record to a person. The record skeleton survives for lineage and audit; its ability to identify anyone does not. The erasure itself is audited in an append-only log of keyed hashes, so Compliance can prove *that* a subject was forgotten without ever re-exposing who they were.

The single sentence behind all three regimes is the one Risk & Compliance and the front office already agreed on: every record has to be accountable.

## How Meridian sees its data

Meridian is a firm in which every department's work is data, but no two departments produce data the same way. Trading streams it. Finance uploads it. Sales pulls it. Without a single accounting of truth, we would be running on three competing pictures of ourselves.

The data platform — documented in detail under [`planning/`](planning/) — is the **connective tissue** that lets every team trust the same numbers. The principle behind it is the one Risk & Compliance and the front office already agreed on: every record has to be accountable, every change has to be reconstructible, and history is never edited. Corrections arrive as new events and are replayed forward; any run can be put under a microscope long after the fact and walked through end to end. That is not a platform design choice. It is a Meridian operating principle, and the platform is what makes it operational.

## Meridian in motion

A handful of short scenes that show the firm in motion, drawn from real moments the platform was built to handle.

### A flagged trade

A client orders $1,500 of NVDA through an advisor. The order hits the trading database, change-data-capture streams it off the moment it lands, and the fraud model scores it against the per-instrument calibration. NVDA's alert threshold is tuned tight — the model trips at trade sizes a fraction of what would matter for AAPL — and the score crosses 0.9. A high-severity alert lands in Risk & Compliance's queue with a link back to the run that scored it. R&C reads the context, finds it consistent with a pattern they have been watching, and hands the case to the **Financial Crime Unit**. The FCU opens a formal case; if the pattern holds, it becomes a regulatory filing.

### A quarantined payroll workbook

James Beringer in **People Operations** uploads a payroll workbook the morning after pay cycle close. The file passes the malware scan, the MIME-type check, and the size gate — but when schema validation runs, the *net_amount* column is missing. The platform never lets the file into the lakehouse; it is set aside in **quarantine**, and an alert fires. The alert routes to People Ops so they can correct the workbook and resubmit, and it also routes to **Risk & Compliance**, because a rejected financial load is itself an auditable event that has to live in the firm's record.

### A late settlement backfill

A batch of loan disbursements settled yesterday but did not reach the OLTP database in time — a core-banking maintenance window held them up overnight. The trades exist; their settlement timestamps exist; only the journey was late. The fraud team needs them posted with their *original* settlement timestamps so daily fraud-scoring metrics and the *loan_status_history* lineage reflect the true settlement date for regulatory reporting. **Data Platform / SRE** triggers a backfill — a controlled, distinctly tagged replay of historical data through the same validated pipelines as live traffic. The records flow through; gold KPIs recompute against de-duplicated tables; the executive dashboards stay correct.

### A corrected commission file

**Compensation Operations** discovers, mid-month, that the March commission adjustment file for Advisor Region 7 was submitted with currency codes in GBP instead of USD — a spreadsheet template error. The original file was quarantined at validation time, exactly as designed. Finance corrects the template, confirms the numbers, and RevOps reissues the file with its original March effective dates. The replay flows through the same pipeline; *kpi_commission_economics* and the downstream Q1 compensation reporting come back into alignment.
