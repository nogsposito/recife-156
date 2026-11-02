-- title: Chamados por dia e grupo, ao lado da chuva do dia
-- question: A chuva muda o volume de chamados de cada grupo de serviço?
-- Tickets are counted per day and group first, and only then matched to the calendar grid
-- (every day x every group), where missing combinations become zero.
WITH daily_counts AS (
    SELECT t.opened_on, s.group_name, COUNT(*) AS tickets
    FROM fact_tickets AS t
    JOIN dim_service AS s USING (service_code)
    GROUP BY t.opened_on, s.group_name
),
calendar AS (
    SELECT date_key, precipitation_mm
    FROM dim_date
    WHERE date_key BETWEEN (SELECT MIN(opened_on) FROM fact_tickets)
                       AND (SELECT MAX(opened_on) FROM fact_tickets)
),
service_groups AS (
    SELECT DISTINCT group_name FROM dim_service
)
SELECT
    c.date_key AS day,
    c.precipitation_mm AS rain_mm,
    g.group_name,
    COALESCE(dc.tickets, 0) AS tickets
FROM calendar AS c
CROSS JOIN service_groups AS g
LEFT JOIN daily_counts AS dc
    ON dc.opened_on = c.date_key
   AND dc.group_name = g.group_name
ORDER BY day, g.group_name;
