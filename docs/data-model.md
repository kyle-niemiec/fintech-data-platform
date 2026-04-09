# Data Model

> **Status:** This document describes the target state for Phases 7–9 (Trino + Iceberg lakehouse). No bronze, silver, or gold tables exist in the current build — only the control plane metadata tables (`ingestion_run`, `artifact`, `lineage_record`) described in [architecture.md](architecture.md) are implemented today. The Trino role names referenced below (`data_engineer`, `analyst`, `executive`, `trino_etl`) are Trino-side roles to be defined when Phase 7 lands; they are not the Postgres `data_analyst` / `data_executive` stub roles in [infra/db/migrations/04_create_roles.sql](../infra/db/migrations/04_create_roles.sql). See [roadmap.md](roadmap.md) for sequencing.

Meridian Capital is a B2B fintech lender that provides working capital loans (term loans, lines of credit, equipment finance) to small and mid-market businesses. The data platform ingests from three source systems, normalizes through a bronze → silver → gold lakehouse, and surfaces business metrics to internal consumers via Trino.

---

## Source Systems

### Source 1: Excel Upload — Commission Clawback Submissions

**Business context:** Sales reps earn a commission (~1% of funded amount) when a loan closes and funds. Finance's commission system (ADP) has no integration with the internal Loan Management System. Each month, a finance analyst runs a lookback report: any loan that goes delinquent or pays off early within 180 days triggers a commission adjustment. Clawbacks are calculated manually in Excel, approved by VP Finance (captured as an `approval_reference` ticket), and uploaded through the data platform.

The data platform consumes this for two purposes: (1) accurate origination P&L — effective commission cost per loan including clawbacks, and (2) compensation analytics — risk-adjusted commission tracking per rep.

**What finance puts in the sheet** (only business fields; operational metadata is captured by the ingestion system):

| Field | Type | Notes |
|---|---|---|
| `rep_employee_id` | string | ADP employee ID — not a name |
| `loan_id` | string | LMS loan identifier (format: LN-YYYYMMDD-XXXXX) |
| `salesforce_opportunity_id` | string | Finance looks this up manually to enable CRM joins |
| `adjustment_type` | string | `commission_clawback_default`, `commission_clawback_early_payoff`, `commission_correction`, `override_bonus` |
| `adjustment_basis` | string | Trigger: `90_dpd`, `180_dpd`, `early_payoff_90d`, `manual_error_correction` |
| `original_commission_paid` | decimal | What ADP paid out |
| `adjustment_amount` | decimal | Negative = clawback, positive = additional payout |
| `effective_payroll_period` | string | YYYY-MM — which payroll cycle this posts to |
| `approval_reference` | string | Internal approval ticket (Jira ID or similar) |
| `notes` | string | Optional free text (e.g., "Waived per CFO — borrower paid in full") |

---

### Source 2: Salesforce CRM — Loan Origination Pipeline

**Business context:** The sales team manages all borrower relationships and loan deals in Salesforce. Every funded loan originates as a Salesforce Opportunity. The data platform uses CRM data for pipeline analytics, conversion tracking, and for linking CRM deals to actual funded loan performance in the LMS.

**Setup:** Standard Salesforce CRM (not Financial Services Cloud). Account = borrower company. Opportunity = loan deal. Contact = signatories and key decision-makers at the borrower. Custom fields added for lending data.

**Extraction method:** Airflow batch job using SOQL with `SystemModstamp >= last_run_ts` for incremental pulls. Deleted records pulled via the Salesforce `/sobjects/{sObject}/deleted/` endpoint. Timestamps use ISO8601 UTC format (`2024-04-07T15:30:45.000+0000`). `SystemModstamp` is used for CDC sync (indexed; captures changes by any process, not just last user).

**API response envelope:**
```json
{
  "totalSize": 42,
  "done": true,
  "records": [
    {
      "attributes": { "type": "Account", "url": "/services/data/v66.0/sobjects/Account/..." },
      "Id": "001D000000IRFmaIAH",
      ...
    }
  ]
}
```

#### Account Object

| SF API Name | Type | Notes |
|---|---|---|
| `Id` | VARCHAR(18) | Salesforce 18-char unique ID (natural key) |
| `Name` | VARCHAR(255) | Borrower company name |
| `Type` | VARCHAR(40) | Prospect, Customer, Partner |
| `Industry` | VARCHAR(40) | Picklist; raw value; normalized to controlled vocab in silver |
| `BillingCountry` | VARCHAR(40) | Free text; normalized to ISO 3166-1 alpha-2 in silver |
| `BillingCountryCode` | VARCHAR(3) | ISO code when populated by Salesforce |
| `BillingState` | VARCHAR(20) | |
| `AnnualRevenue` | DECIMAL(18,0) | Stated by borrower |
| `NumberOfEmployees` | INTEGER | |
| `OwnerId` | VARCHAR(18) | Salesforce User ID of account owner |
| `Annual_Revenue_Verified__c` | BOOLEAN | Custom — has finance verified stated revenue |
| `Risk_Category__c` | VARCHAR(2) | Custom — internal risk tier: A, B, C, D |
| `Existing_Customer__c` | BOOLEAN | Custom — repeat vs new borrower |
| `IsDeleted` | BOOLEAN | Salesforce logical delete |
| `CreatedDate` | TIMESTAMP | ISO8601 UTC |
| `LastModifiedDate` | TIMESTAMP | ISO8601 UTC |
| `SystemModstamp` | TIMESTAMP | Indexed; used for CDC sync |

#### Opportunity Object

| SF API Name | Type | Notes |
|---|---|---|
| `Id` | VARCHAR(18) | Natural key |
| `Name` | VARCHAR(255) | e.g., "ABC Corp — $500K Term Loan" |
| `AccountId` | VARCHAR(18) | FK → Account; may be missing on legacy records |
| `OwnerId` | VARCHAR(18) | |
| `Amount` | DECIMAL(18,2) | Loan amount; schema drift risk — occasionally arrives as string |
| `CloseDate` | DATE | Expected close date; required by Salesforce |
| `StageName` | VARCHAR(40) | Prospect → Qualification → Underwriting → Approval Pending → Documentation → Funded → Declined |
| `Probability` | DECIMAL(5,2) | Auto-calculated from stage |
| `ForecastCategoryName` | VARCHAR(40) | Read-only: Pipeline / Best Case / Commit / Closed |
| `LeadSource` | VARCHAR(40) | Web, Phone Inquiry, Referral, Trade Show |
| `LastStageChangeDate` | TIMESTAMP | |
| `IsClosed` | BOOLEAN | Read-only |
| `IsWon` | BOOLEAN | Read-only |
| `IsDeleted` | BOOLEAN | |
| `Loan_Type__c` | VARCHAR(40) | Custom: term_loan, line_of_credit, equipment_finance |
| `Requested_Term_Months__c` | INTEGER | Custom |
| `Interest_Rate__c` | DECIMAL(6,4) | Custom; e.g., 0.0825 = 8.25% |
| `Underwriting_Status__c` | VARCHAR(20) | Custom: not_started, in_review, approved, declined |
| `CreatedDate` | TIMESTAMP | |
| `LastModifiedDate` | TIMESTAMP | |
| `SystemModstamp` | TIMESTAMP | |

#### Contact Object (PII)

| SF API Name | Type | Notes |
|---|---|---|
| `Id` | VARCHAR(18) | Natural key |
| `AccountId` | VARCHAR(18) | Lookup (optional — Contact can exist without an Account) |
| `OwnerId` | VARCHAR(18) | |
| `FirstName` | VARCHAR(40) | **PII** |
| `LastName` | VARCHAR(80) | **PII**; required by Salesforce |
| `Email` | VARCHAR(255) | **PII** |
| `Phone` | VARCHAR(40) | **PII** |
| `MobilePhone` | VARCHAR(40) | **PII** |
| `Title` | VARCHAR(128) | Job title |
| `Department` | VARCHAR(80) | |
| `IsDeleted` | BOOLEAN | |
| `CreatedDate` | TIMESTAMP | |
| `LastModifiedDate` | TIMESTAMP | |
| `SystemModstamp` | TIMESTAMP | |

---

### Source 3: Loan Management System CDC — Internal Postgres

**Business context:** Meridian Capital's Loan Management System (LMS) is a Postgres monolith built in 2019. It is the source of truth for all funded loan activity: payment processing, status tracking, fee assessment. As the portfolio grew, nightly batch ETL became too slow — the risk team needs to react to large-loan delinquency events within hours, not overnight. The data team deployed Debezium CDC on the LMS Postgres instance in 2023, publishing change events to Kafka. Two LMS tables are captured.

Together with CRM and Excel data, the LMS enables a complete picture of loan economics: what was expected (CRM pipeline), what cleared (LMS payments), and what origination actually cost (commission adjustments).

**Debezium event envelope:**
```json
{
  "op": "u",
  "ts_ms": 1712500000000,
  "source": { "db": "lms", "table": "loan_payments", "ts_ms": 1712499999000 },
  "before": { "...": "..." },
  "after": { "...": "..." }
}
```
`op` values: `c` (insert), `u` (update), `d` (delete). `before` is null on inserts; `after` is null on hard deletes.

#### lms.loans — Loan Master Records

| Field | Type | Notes |
|---|---|---|
| `loan_id` | VARCHAR | PK; format LN-YYYYMMDD-XXXXX |
| `salesforce_opportunity_id` | VARCHAR(18) | Set when loan is created from a funded Opportunity |
| `account_id` | VARCHAR | Mirrors Salesforce Account `Id` |
| `loan_type` | VARCHAR | term_loan, line_of_credit, equipment_finance |
| `principal_amount` | DECIMAL(18,2) | Original funded amount; immutable after origination |
| `interest_rate` | DECIMAL(6,4) | Annualized; e.g., 0.0825 = 8.25% |
| `term_months` | INTEGER | |
| `origination_date` | DATE | Funding date |
| `maturity_date` | DATE | Calculated; immutable |
| `loan_status` | VARCHAR | current, delinquent_30, delinquent_60, delinquent_90, default, paid_off, charged_off |
| `days_past_due` | INTEGER | Recalculated each billing cycle |
| `outstanding_principal` | DECIMAL(18,2) | Decreases with each payment |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | Last update; used for Debezium capture ordering |

#### lms.loan_payments — Payment Events

| Field | Type | Notes |
|---|---|---|
| `payment_id` | VARCHAR | PK |
| `loan_id` | VARCHAR | FK → loans |
| `payment_type` | VARCHAR | scheduled_payment, prepayment, partial_payment, late_fee, nsf_fee, payoff, reversal |
| `due_date` | DATE | When this installment was due |
| `payment_date` | DATE | When payment posted |
| `scheduled_amount` | DECIMAL(18,2) | What was owed |
| `payment_amount` | DECIMAL(18,2) | What was received (differs for partial payments) |
| `principal_applied` | DECIMAL(18,2) | |
| `interest_applied` | DECIMAL(18,2) | |
| `fee_applied` | DECIMAL(18,2) | Late fee or NSF fee component |
| `payment_method` | VARCHAR | ach, wire, check, internal_transfer |
| `ach_return_code` | VARCHAR | Nullable; R01 (NSF), R02 (account closed), R03 (no account), etc. |
| `payment_status` | VARCHAR | pending, cleared, returned, reversed |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

---

## Lakehouse Stages

### Landing

Raw files and events stored as-received in MinIO. No transformation. One artifact record created per file.

```
landing/{run_id}/commission_adjustments_{YYYYMMDD}.xlsx
landing/{run_id}/sf_accounts_{YYYYMMDD}.json
landing/{run_id}/sf_opportunities_{YYYYMMDD}.json
landing/{run_id}/sf_contacts_{YYYYMMDD}.json
landing/{run_id}/lms_loans_{YYYYMMDD_HHMMSS}.json
landing/{run_id}/lms_loan_payments_{YYYYMMDD_HHMMSS}.json
```

---

### Raw

Schema-validated. Type coercion attempted. Valid rows promoted to CSV/JSON. Quarantine on unrecoverable errors.

**Quarantine conditions:**

| Source | Condition |
|---|---|
| Excel | Missing `rep_employee_id`, `loan_id`, or `adjustment_amount` |
| Excel | `adjustment_amount` not parseable as decimal |
| Excel | `effective_payroll_period` not in YYYY-MM format |
| Excel | `adjustment_type` not in controlled vocabulary |
| Salesforce | Missing `Id` (any object type) |
| Salesforce | `Amount` (Opportunity) non-numeric after coercion attempt |
| Salesforce | `CloseDate` (Opportunity) not parseable as DATE |
| Salesforce | Missing `LastName` (Contact) |
| CDC | `op` not in `{c, u, d}` |
| CDC | Missing `loan_id` / `payment_id` on c/u events |
| CDC | `cdc_ts_ms` missing or non-numeric |
| CDC | Duplicate `payment_id` + `cdc_ts_ms` | Deduplicated, not quarantined |
| Any | >20% of rows in a file quarantined | Run marked `failed` |

---

### Bronze (Iceberg, Append-Only)

Parquet, schema-enforced, source-faithful with run metadata appended. Six tables in the `bronze` Iceberg schema.

#### bronze.sf_account_raw
```
Id                          VARCHAR(18)
Name                        VARCHAR(255)
Type                        VARCHAR(40)
Industry                    VARCHAR(40)     -- raw picklist value
BillingCountry              VARCHAR(40)     -- raw free text
BillingCountryCode          VARCHAR(3)
BillingState                VARCHAR(20)
AnnualRevenue               DECIMAL(18,0)
NumberOfEmployees           INTEGER
OwnerId                     VARCHAR(18)
Annual_Revenue_Verified__c  BOOLEAN
Risk_Category__c            VARCHAR(2)
Existing_Customer__c        BOOLEAN
IsDeleted                   BOOLEAN
CreatedDate                 TIMESTAMP
LastModifiedDate            TIMESTAMP
SystemModstamp              TIMESTAMP       -- CDC sync field
run_id                      UUID
extracted_at                TIMESTAMP
```

#### bronze.sf_opportunity_raw
```
Id                          VARCHAR(18)
Name                        VARCHAR(255)
AccountId                   VARCHAR(18)     -- may be null on legacy records
OwnerId                     VARCHAR(18)
Amount                      DECIMAL(18,2)   -- type-coerced from raw
CloseDate                   DATE
StageName                   VARCHAR(40)
Probability                 DECIMAL(5,2)
ForecastCategoryName        VARCHAR(40)
LeadSource                  VARCHAR(40)
IsClosed                    BOOLEAN
IsWon                       BOOLEAN
IsDeleted                   BOOLEAN
LastStageChangeDate         TIMESTAMP
Loan_Type__c                VARCHAR(40)
Requested_Term_Months__c    INTEGER
Interest_Rate__c            DECIMAL(6,4)
Underwriting_Status__c      VARCHAR(20)
CreatedDate                 TIMESTAMP
LastModifiedDate            TIMESTAMP
SystemModstamp              TIMESTAMP
run_id                      UUID
extracted_at                TIMESTAMP
```

#### bronze.sf_contact_raw
```
Id                          VARCHAR(18)
AccountId                   VARCHAR(18)     -- nullable; lookup not master-detail
OwnerId                     VARCHAR(18)
FirstName                   VARCHAR(40)     -- PII
LastName                    VARCHAR(80)     -- PII
Email                       VARCHAR(255)    -- PII
Phone                       VARCHAR(40)     -- PII
MobilePhone                 VARCHAR(40)     -- PII
Title                       VARCHAR(128)
Department                  VARCHAR(80)
IsDeleted                   BOOLEAN
CreatedDate                 TIMESTAMP
LastModifiedDate            TIMESTAMP
SystemModstamp              TIMESTAMP
run_id                      UUID
extracted_at                TIMESTAMP
```

#### bronze.lms_loan_raw
```
loan_id                     VARCHAR
salesforce_opportunity_id   VARCHAR(18)
account_id                  VARCHAR         -- mirrors SF Account.Id
loan_type                   VARCHAR
principal_amount            DECIMAL(18,2)
interest_rate               DECIMAL(6,4)
term_months                 INTEGER
origination_date            DATE
maturity_date               DATE
loan_status                 VARCHAR
days_past_due               INTEGER
outstanding_principal       DECIMAL(18,2)
lms_created_at              TIMESTAMP
lms_updated_at              TIMESTAMP
cdc_op                      VARCHAR(1)      -- c, u, d
cdc_ts_ms                   BIGINT          -- Debezium source timestamp (epoch ms)
run_id                      UUID
ingested_at                 TIMESTAMP
```

#### bronze.lms_loan_payment_raw
```
payment_id                  VARCHAR
loan_id                     VARCHAR
payment_type                VARCHAR
due_date                    DATE
payment_date                DATE
scheduled_amount            DECIMAL(18,2)
payment_amount              DECIMAL(18,2)
principal_applied           DECIMAL(18,2)
interest_applied            DECIMAL(18,2)
fee_applied                 DECIMAL(18,2)
payment_method              VARCHAR
ach_return_code             VARCHAR         -- nullable
payment_status              VARCHAR
lms_created_at              TIMESTAMP
lms_updated_at              TIMESTAMP
cdc_op                      VARCHAR(1)
cdc_ts_ms                   BIGINT
run_id                      UUID
ingested_at                 TIMESTAMP
```

#### bronze.commission_adjustment_raw
```
rep_employee_id             VARCHAR
loan_id                     VARCHAR
salesforce_opportunity_id   VARCHAR(18)
adjustment_type             VARCHAR
adjustment_basis            VARCHAR
original_commission_paid    DECIMAL(18,2)
adjustment_amount           DECIMAL(18,4)
effective_payroll_period    VARCHAR(7)      -- YYYY-MM
approval_reference          VARCHAR
notes                       VARCHAR         -- nullable; may contain free text
run_id                      UUID
source_file                 VARCHAR         -- captured by ingestion system
uploaded_at                 TIMESTAMP       -- captured by ingestion system
```

---

### Silver PII (Normalized, 3NF, SCD Type 2)

Accessible only to `data_engineer` and `trino_etl`. Contains PII. Business logic, normalization, deduplication, and SCD Type 2 merges all occur here.

#### Normalization Rationale (3NF)

All tables use single-column surrogate primary keys (`*_sk`). No composite primary keys (2NF satisfied by definition).

3NF holds across the schema:

- **dim_account:** All non-key attributes depend solely on `account_sf_id`. Contact PII (email, phone) is isolated in `dim_contact` — no transitive dependency through the account natural key.
- **dim_opportunity:** All attributes depend on `opportunity_sf_id`. `account_sk` is a foreign key reference only — no account attributes (name, industry) are repeated.
- **dim_contact:** All attributes depend on `contact_sf_id`. `account_sf_id` is a natural key reference (deliberately not `account_sk` — the natural key survives SCD rotations that change the surrogate).
- **dim_loan:** Loan terms (`principal_amount`, `interest_rate`, `term_months`, `origination_date`, `maturity_date`) all depend on `loan_id`. Status is not stored here — status changes are events in `loan_status_history`.
- **fact_loan_payment:** All fields are properties of the payment event (`payment_id`). FK references only — no dimension attributes repeated.
- **fact_commission_adjustment:** Properties of the adjustment event. FK references to dimensions. `notes` dropped (free text, potential PII — retained in bronze).
- **loan_status_history:** Append-only status transition events. Each row records a detected change. No dimension attributes repeated.

#### SCD Type 2 — Tracked Fields

| Table | Fields Triggering a New Version |
|---|---|
| `dim_account` | `Name`, `Type`, `Industry` (normalized), `BillingCountry` (normalized), `Risk_Category__c`, `OwnerId` |
| `dim_contact` | `Email`, `Phone`, `MobilePhone`, `Title`, `Department` |
| `dim_opportunity` | `StageName`, `Amount`, `Probability`, `CloseDate`, `Underwriting_Status__c`, `IsClosed`, `IsWon` |
| `dim_loan` | Not applicable — loan terms are immutable after origination |
| `dim_sales_rep` | Not applicable — no tracked attributes in current schema |

#### SCD Type 2 Merge Logic

```
FOR EACH incoming record (ordered by SystemModstamp or lms_updated_at):

  1. Look up current row WHERE natural_key = ? AND is_current = true
  2. No match → INSERT new row
       valid_from = source_ts, valid_to = NULL, is_current = true
  3. Match + no trigger field changed → no-op (idempotent)
  4. Match + trigger field changed:
       a. UPDATE existing: SET valid_to = source_ts, is_current = false
       b. INSERT new: valid_from = source_ts, valid_to = NULL, is_current = true
  5. IsDeleted = true (Salesforce):
       a. UPDATE existing: SET valid_to = source_ts, is_current = false
       b. No new insert (GDPR — record is logically gone)
```

#### silver_pii.dim_account
```
account_sk              BIGINT           -- surrogate PK
account_sf_id           VARCHAR(18)      -- natural key (Salesforce Account.Id)
account_name            VARCHAR(255)
account_type            VARCHAR(40)
industry_normalized     VARCHAR(50)      -- standardized via lookup map
billing_country_code    VARCHAR(2)       -- ISO 3166-1 alpha-2; normalized
billing_state           VARCHAR(20)
annual_revenue          DECIMAL(18,0)
employee_count          INTEGER
risk_category           VARCHAR(2)       -- A, B, C, D
owner_sf_id             VARCHAR(18)
annual_revenue_verified BOOLEAN
existing_customer       BOOLEAN
is_deleted              BOOLEAN
valid_from              TIMESTAMP
valid_to                TIMESTAMP        -- NULL = current record
is_current              BOOLEAN
first_seen_run_id       UUID
last_changed_run_id     UUID
```

#### silver_pii.dim_contact (PII isolated)
```
contact_sk              BIGINT
contact_sf_id           VARCHAR(18)      -- natural key
account_sf_id           VARCHAR(18)      -- natural key ref; not account_sk (survives SCD rotation)
first_name              VARCHAR(40)      -- PII
last_name               VARCHAR(80)      -- PII
email                   VARCHAR(255)     -- PII
phone                   VARCHAR(40)      -- PII
mobile_phone            VARCHAR(40)      -- PII
title                   VARCHAR(128)
department              VARCHAR(80)
is_deleted              BOOLEAN
valid_from              TIMESTAMP
valid_to                TIMESTAMP
is_current              BOOLEAN
last_changed_run_id     UUID
```

#### silver_pii.dim_opportunity
```
opportunity_sk          BIGINT
opportunity_sf_id       VARCHAR(18)      -- natural key
account_sk              BIGINT           -- FK → dim_account (current SK at merge time)
owner_sf_id             VARCHAR(18)
opportunity_name        VARCHAR(255)
loan_type               VARCHAR(40)
requested_amount        DECIMAL(18,2)
requested_term_months   INTEGER
interest_rate           DECIMAL(6,4)
stage                   VARCHAR(40)
probability             DECIMAL(5,2)
close_date              DATE
underwriting_status     VARCHAR(20)
lead_source             VARCHAR(40)
is_closed               BOOLEAN
is_won                  BOOLEAN
is_deleted              BOOLEAN
valid_from              TIMESTAMP
valid_to                TIMESTAMP
is_current              BOOLEAN
first_seen_run_id       UUID
last_changed_run_id     UUID
```

#### silver_pii.dim_loan
```
loan_sk                 BIGINT
loan_id                 VARCHAR          -- LN-YYYYMMDD-XXXXX (natural key)
opportunity_sk          BIGINT           -- FK → dim_opportunity (current SK at origination)
account_sk              BIGINT           -- FK → dim_account (current SK at origination)
loan_type               VARCHAR
principal_amount        DECIMAL(18,2)
interest_rate           DECIMAL(6,4)
term_months             INTEGER
origination_date        DATE
maturity_date           DATE
first_seen_run_id       UUID
```

No SCD Type 2 — loan terms are contractually immutable after origination. Status changes are tracked as events in `loan_status_history`.

#### silver_pii.loan_status_history (append-only)
```
status_event_sk         BIGINT
loan_id                 VARCHAR          -- natural key ref
loan_sk                 BIGINT           -- FK → dim_loan
previous_status         VARCHAR          -- NULL on first recorded event per loan
current_status          VARCHAR
days_past_due           INTEGER
outstanding_principal   DECIMAL(18,2)    -- balance at time of status change
effective_at            TIMESTAMP        -- from lms_updated_at
run_id                  UUID
ingested_at             TIMESTAMP
```

Processing rule: Insert a new row only when `loan_status` or `days_past_due` differs from the prior event for that `loan_id`. Skip updates that change other LMS columns without changing status (Debezium fires on any column update).

#### silver_pii.dim_sales_rep
```
rep_sk                  BIGINT
rep_employee_id         VARCHAR          -- ADP employee ID (natural key)
valid_from              TIMESTAMP
valid_to                TIMESTAMP
is_current              BOOLEAN
last_changed_run_id     UUID
```

Stub. No PII in current data sources for this dimension. Expands when HR system integrates.

#### silver_pii.fact_loan_payment
```
payment_sk              BIGINT
payment_id              VARCHAR          -- LMS natural key (dedup key)
loan_sk                 BIGINT           -- FK → dim_loan
payment_type            VARCHAR
due_date                DATE
payment_date            DATE
scheduled_amount        DECIMAL(18,2)
payment_amount          DECIMAL(18,2)
principal_applied       DECIMAL(18,2)
interest_applied        DECIMAL(18,2)
fee_applied             DECIMAL(18,2)
payment_method          VARCHAR          -- sensitive: ach, wire, check, internal_transfer
ach_return_code         VARCHAR          -- sensitive: R01, R02, R03...
payment_status          VARCHAR
cdc_ts_ms               BIGINT
run_id                  UUID
ingested_at             TIMESTAMP
```

Deduplication: Same `payment_id` + `cdc_ts_ms` → skip. Same `payment_id` + newer `cdc_ts_ms` (update or reversal event) → append new row. Full event history is preserved; at-least-once delivery is handled.

#### silver_pii.fact_commission_adjustment
```
adjustment_sk           BIGINT
rep_sk                  BIGINT           -- FK → dim_sales_rep; NULL if unresolvable
loan_sk                 BIGINT           -- FK → dim_loan; NULL if unresolvable
opportunity_sk          BIGINT           -- FK → dim_opportunity; NULL if unresolvable
adjustment_type         VARCHAR
adjustment_basis        VARCHAR
original_commission_paid DECIMAL(18,2)
adjustment_amount       DECIMAL(18,4)
effective_payroll_period VARCHAR(7)
approval_reference      VARCHAR
run_id                  UUID
ingested_at             TIMESTAMP
```

`notes` is dropped in silver. Free text with potential PII references. The bronze record retains it for audit.

---

### Data Quality Rules (Bronze → Silver)

| Issue | Handling |
|---|---|
| `Industry` free-text inconsistencies | Normalize via case-insensitive lookup map; unmapped → `'unclassified'` |
| `BillingCountry` variations | ISO 3166 lookup (country name → alpha-2 code); unmapped → `'XX'` |
| `AccountId` in Opportunity missing from dim_account | Persist with `account_sk = NULL`; log DQ warning |
| `loan_id` in commission_adjustment missing from dim_loan | Persist with `loan_sk = NULL`; log DQ warning |
| `salesforce_opportunity_id` in commission_adjustment not in dim_opportunity | Persist with `opportunity_sk = NULL`; log DQ warning |
| Duplicate `payment_id` same `cdc_ts_ms` | Skip (dedup) |
| Duplicate `payment_id` newer `cdc_ts_ms` | Append (full event history) |
| Out-of-order CDC events | Order by `cdc_ts_ms` before processing |
| LMS update with no status change | Skip insert to `loan_status_history` (debounce) |
| `Amount` arrives as string in Opportunity | Coerce at raw stage; quarantine if fails |
| `IsDeleted = true` on Salesforce record | Close current SCD record; no new insert (GDPR) |

---

### Silver Views (De-identified, `analyst` role)

Views over `silver_pii.*`. PII is excluded by view definition — not by column masking. Column masks in `rules.json` are belt-and-suspenders and will be finalized in Phase 8 once Iceberg table column names are confirmed.

| View | Source Table | Exclusions |
|---|---|---|
| `silver.dim_account` | `silver_pii.dim_account` | None (no PII in this table) |
| `silver.dim_opportunity` | `silver_pii.dim_opportunity` | None |
| `silver.dim_loan` | `silver_pii.dim_loan` | None |
| `silver.loan_status_history` | `silver_pii.loan_status_history` | None |
| `silver.dim_sales_rep` | `silver_pii.dim_sales_rep` | None (no PII in current schema) |
| `silver.fact_loan_payment` | `silver_pii.fact_loan_payment` | `ach_return_code` excluded; `payment_method` retained for NSF analysis |
| `silver.fact_commission_adjustment` | `silver_pii.fact_commission_adjustment` | None (`notes` dropped at silver_pii) |

`dim_contact` is not exposed in the `silver` schema at all. No analyst-accessible view.

---

### Gold (KPIs, Aggregated)

Accessible to `analyst` and `executive` Trino roles. No individual-level rows. No PII. No operationally sensitive fields.

#### gold.kpi_portfolio_health
```
period_month            DATE
loan_type               VARCHAR
industry_normalized     VARCHAR
billing_country_code    VARCHAR(2)
loan_count              BIGINT
total_principal         DECIMAL(18,2)
avg_outstanding_principal DECIMAL(18,2)
current_count           BIGINT
delinquent_30_count     BIGINT
delinquent_60_count     BIGINT
delinquent_90_count     BIGINT
default_count           BIGINT
paid_off_count          BIGINT
charged_off_count       BIGINT
```

#### gold.kpi_payment_performance
```
period_month            DATE
loan_type               VARCHAR
payment_type            VARCHAR
payment_method_category VARCHAR       -- electronic (ach/wire/internal_transfer), paper (check)
scheduled_total         DECIMAL(18,2)
received_total          DECIMAL(18,2)
collection_rate         DECIMAL(5,4)  -- received / scheduled
returned_count          BIGINT
returned_amount         DECIMAL(18,2)
fee_revenue             DECIMAL(18,2)
```

#### gold.kpi_pipeline_conversion
```
period_month            DATE
stage                   VARCHAR
loan_type               VARCHAR
industry_normalized     VARCHAR
opportunity_count       BIGINT
total_requested_amount  DECIMAL(18,2)
avg_probability         DECIMAL(5,2)
funded_count            BIGINT
funded_amount           DECIMAL(18,2)
declined_count          BIGINT
```

#### gold.kpi_commission_economics
```
period_month            DATE
adjustment_type         VARCHAR
adjustment_count        BIGINT
total_original_commission DECIMAL(18,2)
total_adjustment        DECIMAL(18,4)
net_commission_impact   DECIMAL(18,4)
```

No rep-level data at the gold layer.

---

## PII Inventory

| Field | Source | Bronze Table | Silver PII Table | Silver View? | Gold? |
|---|---|---|---|---|---|
| `FirstName` | Salesforce Contact | `sf_contact_raw` | `dim_contact` | No | No |
| `LastName` | Salesforce Contact | `sf_contact_raw` | `dim_contact` | No | No |
| `Email` (contact) | Salesforce Contact | `sf_contact_raw` | `dim_contact` | No | No |
| `Phone` (contact) | Salesforce Contact | `sf_contact_raw` | `dim_contact` | No | No |
| `MobilePhone` | Salesforce Contact | `sf_contact_raw` | `dim_contact` | No | No |
| `notes` (free text) | Excel | `commission_adjustment_raw` | Not persisted | No | No |
| `ach_return_code` | LMS CDC | `lms_loan_payment_raw` | `fact_loan_payment` | No | No |

`payment_method` (ach, wire, check) is operationally sensitive but not PII. Retained in `silver.fact_loan_payment` for NSF analysis. Abstracted to `payment_method_category` (electronic / paper) in gold.
