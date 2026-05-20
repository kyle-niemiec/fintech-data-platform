ALTER TABLE trading.loan
ADD COLUMN IF NOT EXISTS original_principal_balance NUMERIC(18, 2);

UPDATE trading.loan
SET original_principal_balance = principal_balance
WHERE original_principal_balance IS NULL;

ALTER TABLE trading.loan
ALTER COLUMN original_principal_balance SET NOT NULL;
