-- title: Tempo de resolução por região (RPA) nos maiores grupos
-- question: Dentro de um mesmo tipo de serviço, alguma região espera mais?
WITH top_groups AS (
    SELECT s.group_code
    FROM fact_tickets AS t
    JOIN dim_service AS s USING (service_code)
    GROUP BY s.group_code
    ORDER BY COUNT(*) DESC
    LIMIT 4
)
SELECT
    s.group_name,
    n.rpa,
    COUNT(*) AS resolved_tickets,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.days_to_last_update) AS median_days,
    PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY t.days_to_last_update) AS p90_days
FROM fact_tickets AS t
JOIN dim_service AS s USING (service_code)
JOIN dim_neighborhood AS n USING (neighborhood_id)
WHERE t.status = 'ATENDIDA'
  AND s.group_code IN (SELECT group_code FROM top_groups)
GROUP BY s.group_name, n.rpa
ORDER BY s.group_name, n.rpa;
