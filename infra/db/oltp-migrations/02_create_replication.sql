DO
$$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'cdc_pub') THEN
        CREATE PUBLICATION cdc_pub
            FOR TABLE trading.transaction, trading.risk_flag;
    END IF;
END;
$$;
