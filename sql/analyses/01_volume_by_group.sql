-- title: Volume por grupo de serviço
-- question: Quais áreas da Emlurb recebem mais demandas?
SELECT
    g.group_name,
    COUNT(*) AS tickets,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_total
FROM tickets AS t
JOIN services AS s USING (service_code)
JOIN service_groups AS g USING (group_code)
GROUP BY g.group_name
ORDER BY tickets DESC;
