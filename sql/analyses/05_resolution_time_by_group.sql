-- title: Tempo de resolução por grupo de serviço
-- question: Quanto tempo cada tipo de serviço leva para ser atendido?
-- Only resolved tickets (status ATENDIDA); open tickets have no resolution time yet.
SELECT
    s.group_name,
    COUNT(*) AS resolved_tickets,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.days_to_last_update) AS median_days,
    PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY t.days_to_last_update) AS p90_days,
    ROUND(100.0 * AVG((t.days_to_last_update <= 7)::int), 1) AS pct_within_7_days
FROM fact_tickets AS t
JOIN dim_service AS s USING (service_code)
WHERE t.status = 'ATENDIDA'
GROUP BY s.group_name
HAVING COUNT(*) >= 100
ORDER BY median_days DESC, p90_days DESC;
