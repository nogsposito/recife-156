-- Read-only access for the text-to-SQL assistant: the gold tables and the dashboard view,
-- nothing else. Reapplied after every gold load, because the tables are recreated.
ALTER ROLE assistant_readonly SET default_transaction_read_only = on;
ALTER ROLE assistant_readonly SET statement_timeout = '10s';
GRANT USAGE ON SCHEMA public TO assistant_readonly;
GRANT SELECT ON dim_service, dim_neighborhood, dim_date, fact_tickets, v_tickets
    TO assistant_readonly;
