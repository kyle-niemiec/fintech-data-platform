#!/bin/bash
# Creates OLTP runtime roles whose passwords come from the container environment.
# Executed once by the Postgres image init phase (docker-entrypoint-initdb.d).
set -euo pipefail

: "${OLTP_APP_USER:?OLTP_APP_USER must be set}"
: "${OLTP_APP_PASSWORD:?OLTP_APP_PASSWORD must be set}"
: "${OLTP_REPLICATION_USER:?OLTP_REPLICATION_USER must be set}"
: "${OLTP_REPLICATION_PASSWORD:?OLTP_REPLICATION_PASSWORD must be set}"
: "${OLTP_UI_READER_USER:?OLTP_UI_READER_USER must be set}"
: "${OLTP_UI_READER_PASSWORD:?OLTP_UI_READER_PASSWORD must be set}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${OLTP_APP_USER}') THEN
        CREATE ROLE ${OLTP_APP_USER} LOGIN PASSWORD '${OLTP_APP_PASSWORD}';
    ELSE
        ALTER ROLE ${OLTP_APP_USER} WITH LOGIN PASSWORD '${OLTP_APP_PASSWORD}';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${OLTP_REPLICATION_USER}') THEN
        CREATE ROLE ${OLTP_REPLICATION_USER} LOGIN REPLICATION PASSWORD '${OLTP_REPLICATION_PASSWORD}';
    ELSE
        ALTER ROLE ${OLTP_REPLICATION_USER} WITH LOGIN REPLICATION PASSWORD '${OLTP_REPLICATION_PASSWORD}';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${OLTP_UI_READER_USER}') THEN
        CREATE ROLE ${OLTP_UI_READER_USER} LOGIN PASSWORD '${OLTP_UI_READER_PASSWORD}';
    ELSE
        ALTER ROLE ${OLTP_UI_READER_USER} WITH LOGIN PASSWORD '${OLTP_UI_READER_PASSWORD}';
    END IF;
END;
\$\$;

GRANT USAGE ON SCHEMA trading TO ${OLTP_APP_USER};
GRANT SELECT, INSERT, UPDATE ON trading.transaction TO ${OLTP_APP_USER};
GRANT SELECT, INSERT, UPDATE ON trading.loan TO ${OLTP_APP_USER};
GRANT SELECT, INSERT, UPDATE ON trading.loan_payment TO ${OLTP_APP_USER};
GRANT SELECT, INSERT, UPDATE ON trading.loan_status_history TO ${OLTP_APP_USER};
GRANT SELECT, INSERT ON trading.risk_flag TO ${OLTP_APP_USER};

-- Debezium replication role needs SELECT on tables in the publication to
-- emit snapshot reads; logical replication itself uses REPLICATION attribute.
GRANT USAGE ON SCHEMA trading TO ${OLTP_REPLICATION_USER};
GRANT SELECT ON
    trading.transaction,
    trading.loan,
    trading.loan_payment,
    trading.loan_status_history,
    trading.risk_flag
TO ${OLTP_REPLICATION_USER};

-- UI reader is read-only and scoped to the two trading tables; no access to
-- app/replication credentials or other schemas.
GRANT USAGE ON SCHEMA trading TO ${OLTP_UI_READER_USER};
GRANT SELECT ON
    trading.transaction,
    trading.loan,
    trading.loan_payment,
    trading.loan_status_history,
    trading.risk_flag
TO ${OLTP_UI_READER_USER};
SQL
