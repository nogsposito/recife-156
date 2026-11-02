-- title: Volume por grupo de serviço
-- question: Quais áreas da Emlurb recebem mais demandas?
SELECT
    s.group_name,
    COUNT(*) AS tickets,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_total
FROM fact_tickets AS t
JOIN dim_service AS s USING (service_code)
GROUP BY s.group_name
ORDER BY tickets DESC;
