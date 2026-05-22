-- Provenance marker for trading.transaction. NULL means a system-generated row
-- (OLTP load generator / app writer); 'manual_demo' marks rows inserted on
-- demand by the UI CDC-demo button. Read directly from OLTP by the query plane;
-- it never needs to traverse CDC, so Debezium/REPLICA IDENTITY is unaffected.
ALTER TABLE trading.transaction
ADD COLUMN IF NOT EXISTS origin TEXT;
