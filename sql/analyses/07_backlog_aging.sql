-- title: Fila de chamados em aberto por idade
-- question: Quanto da fila está parada há muito tempo, e em quais serviços?
-- Age is measured up to the most recent date in the data (the snapshot date).
WITH snapshot AS (
    SELECT MAX(status_updated_on) AS reference_date FROM tickets
),
open_tickets AS (
    SELECT g.group_name, snapshot.reference_date - t.opened_on AS age_days
    FROM tickets AS t
    CROSS JOIN snapshot
    JOIN services AS s USING (service_code)
    JOIN service_groups AS g USING (group_code)
    WHERE t.status <> 'ATENDIDA'
)
SELECT
    group_name,
    COUNT(*) AS open_tickets,
    COUNT(*) FILTER (WHERE age_days <= 30) AS up_to_30_days,
    COUNT(*) FILTER (WHERE age_days BETWEEN 31 AND 180) AS from_31_to_180_days,
    COUNT(*) FILTER (WHERE age_days > 180) AS over_180_days,
    ROUND(100.0 * AVG((age_days > 180)::int), 1) AS pct_over_180_days
FROM open_tickets
GROUP BY group_name
ORDER BY open_tickets DESC
LIMIT 10;
