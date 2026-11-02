-- title: Chamados por dia e grupo com chuva, juntando antes de agregar
-- First version of sql/analyses/09: it joins the calendar grid to every ticket and only
-- then counts, so the join handles all 200 thousand rows. Kept to compare with the rewrite.
-- The CROSS JOIN keeps days without tickets in a group, which count as zero.
WITH service_groups AS (
    SELECT DISTINCT group_name FROM dim_service
)
SELECT
    d.date_key AS day,
    d.precipitation_mm AS rain_mm,
    g.group_name,
    COUNT(t.ticket_id) AS tickets
FROM dim_date AS d
CROSS JOIN service_groups AS g
LEFT JOIN dim_service AS s ON s.group_name = g.group_name
LEFT JOIN fact_tickets AS t
    ON t.service_code = s.service_code
   AND t.opened_on = d.date_key
WHERE d.date_key BETWEEN (SELECT MIN(opened_on) FROM fact_tickets)
                     AND (SELECT MAX(opened_on) FROM fact_tickets)
GROUP BY d.date_key, d.precipitation_mm, g.group_name
ORDER BY day, g.group_name;
