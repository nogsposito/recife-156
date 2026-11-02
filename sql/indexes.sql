-- Created after the bulk load, which is faster than updating them row by row during COPY.
-- docs/sql_optimization.md measures each one with EXPLAIN ANALYZE.

-- Filters by service over a date range (moving averages, daily series of one service)
CREATE INDEX IF NOT EXISTS idx_fact_tickets_service_opened
    ON fact_tickets (service_code, opened_on);

-- Partial index: only open tickets, which is what the operational queue queries look at
CREATE INDEX IF NOT EXISTS idx_fact_tickets_open_by_neighborhood
    ON fact_tickets (neighborhood_id, opened_on)
    WHERE is_open;
