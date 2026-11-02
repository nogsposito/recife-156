-- title: Chamados por dia e grupo, ao lado da chuva do dia
-- question: A chuva muda o volume de chamados de cada grupo de serviço?
-- The CROSS JOIN keeps days without tickets in a group, which count as zero.
SELECT
    w.weather_date AS day,
    w.precipitation_mm AS rain_mm,
    g.group_name,
    COUNT(t.ticket_id) AS tickets
FROM daily_weather AS w
CROSS JOIN service_groups AS g
LEFT JOIN services AS s ON s.group_code = g.group_code
LEFT JOIN tickets AS t
    ON t.service_code = s.service_code
   AND t.opened_on = w.weather_date
GROUP BY w.weather_date, w.precipitation_mm, g.group_name
ORDER BY day, g.group_name;
