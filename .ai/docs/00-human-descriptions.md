# Original Human Concept Notes (Historical Reference)

This document preserves the initial human-written project concept input.
It is historical context only and is non-authoritative for active decisions.
For current product intent and specifications, use `.ai/docs/planning/` first.

---

# Fintech Data Pipeline Project

Ahaha. You're pretty good at guessing what I want to do. We're going to make a fintech data pipeline. The business problem poses 3 disparate sources of data that have to be normalized and aggregated:

- Financial excel files that are manually uploaded which trigger ingestion
- An OLTP database that implements CDC and basic fraud detection
- A Salesforce CRM account that is batched safely 

These 3 sources of information are eventually cleaned and stored in bronze, silver, and gold tiers. Being a fintech pipeline will be the most difficult piece of this project. All pipeline steps have to have a legally defensible system in place for auditing/logging and data privacy. The goal is to meet FINRA and SOC 2 guidelines. Other regulatory frameworks are nice to have, such as GDRP, but are not the goal of this project.

I will also need suggestions on data models, since I am altogether unfamiliar with what type of data a financial institution might hold for each piece. This problem is, however, inspired from a senior data engineer job posting.

I would also like this project to be as close to free as possible, since it is a demo. Selecting the free-tier Salesforce would be an example of a restriction. Many of the technologies I have selected are based on my experience of AWS and I am open to suggestions for ways to make the platform less expensive and more cohesive.

User notifications are normally expected to go through a Slack channel, but I am unsure of the best way to set up demo notifications right now. We could potentially stream to a Slack channel, but I want the feedback from the system to be available to any observing users.

I would like to expose a UI that shows the status of the pipeline and if any information is currently being ingested. This UI should also support the ability to trace any single run of ingestion, displaying the original data format and each step of transformation. This should allow any observer of the project to confirm the auditability of any process run. The UI should allow the user to generate a set of data to be processed. Sometimes this data should be intentionally generated to fail schema or fraud pipelines.

# The inputs

## Manual Excel files

The excel files will be allowed to uploaded into an S3 folder that only users in a finance department have write access to. The upload should trigger an automatic virus check on the file, as well as file size checks and basic type validation.

Once the initial checks have passed, the Excel file will need to be processed through an Airflow script. The Airflow commands will be responsible for schema validation and user alerts. The uploaded file is given the Airflow run ID and either stored in raw storage for tracability, or it is placed in quarantine if validation fails and a notification will be sent out to the finance department.

This data ingestion layer will also need its own, exlusive database for event storage to persist run IDs mapped to raw files. An appropriate database technology should be suggested here. Saved raw files should be named a combination of the original file name and the run ID.

Once the Airflow process is completed and the Excel file is stored successfully, the data is converted into Parquet and passed onto Bronze storage to begin the next steps.

## OLTP database

This database will represent an internal API that the company has for financial transaction processing. As changes are introduced, CDC will run through Debezium or AWS DMS and stream CDC events out to Kafka.

The first subscriber will be a small-but-scalable Kubernetes instance that performs basic fraud detection. For example, something as simple as:

```python
if event.after.amount > 10000 and event.after.instrument == "AAPL":
    flag_transaction(event.after.transaction_id)
````

could trigger a high risk score which should notify the finance department. The original transaction should be flagged in the OLTP database as well.

Once the fraud detection pipeline has been successfully run, a new event is published to Kafka containing the assessed transaction details. As soon as these completed events are received, a subscriber will convert the data to Parquet and export it to Bronze storage for further processing. The exported data must contain the Kafka metadata for tracability, use LSN for ordering/auditing, and perform zero transformation for legal defensibility.

## Salesforce CRM

The third data source will be from a Salesforce CRM account. Specific, sensitive customer data will be pulled in scheduled (or manually initiated from the UI) batches. This is likely going to run from an Airflow script with PythonOperators, but I also have Kafka with Kubernetes listed as an option if streaming events seems like a better option at any point.

Airflow will be in charge of failure retry, incremental pulls (based on last timestamp), failure notifications to Slack, auditable logging, and must process data on a private subnet with no public access.

This stage must also have an event storage which relates timestamped pulls to be associated with the RAW API data that was received by the request to Salesforce for auditability.

As the last step, the data is packaged in Parquet format and sent off to Bronze storage for persistence.

# Bronze/Silver/Gold storage

The persistence layer is arguably one of the most important layers of the system, being in charge of permanent record storage, normalization, SDC 2, and key data transformations.

Data that hits the storage layers should be encypted by the bucket and KMS policies. Using a tool similary to Amazon EventBridge, data should move through a set of Airflow processes that are responsible for transforming and persisting the data in the correct layers sequentially.

## Technology discussion

I have not fully decided on the tech stack for the storage layers, but I am considering the following:

* S3 storage for object versioning, delete protection, write-only role access
* Iceberg+Trino for table abstractions and query engine.
* AWS event-bridge and Airflow for processing and moving data from bronze->silver->gold

Table level controls should define no DELETE or UPDATE privileges, use an append-only table configuration, and enable time traveling. Process controls need to take backfill overwriting into consideration, as well as always reading forward/replaying Kafka events in the need of reprocessing data. If data is wrong, it should never change history, instead it should add a new event.

## Layer descriptions

### Bronze

**Read-access**: Platform and security.
**Purpose**: Auditing, replay, forensics, and compliance.
**Properties**: Append-only, all CDC events, unmasked PII, and highly-limited access.

### Silver

**Read-access**: Analysts and data science.
**Purpose**: Feature engineering and regulatory reports.
**Properties**: Cleaned, normalized, deduplicated, GDPR deletes, masked PII.

### Gold

**Read-access**: BI tools and business executives.
**Purpose**: External reporting and KPIs.
**Properties**: Aggregated, modeled, no direct PII.
