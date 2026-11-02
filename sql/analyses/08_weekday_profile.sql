-- title: Chamados por dia da semana
-- question: Em que dias a central recebe mais demandas?
-- The date dimension counts every calendar day, including days with no tickets.
WITH daily AS (
    SELECT d.date_key, d.day_of_week, COUNT(t.ticket_id) AS tickets
    FROM dim_date AS d
    LEFT JOIN fact_tickets AS t ON t.opened_on = d.date_key
    WHERE d.date_key BETWEEN (SELECT MIN(opened_on) FROM fact_tickets)
                         AND (SELECT MAX(opened_on) FROM fact_tickets)
    GROUP BY d.date_key, d.day_of_week
)
SELECT
    day_of_week AS weekday_number,
    (ARRAY['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'])
        [day_of_week] AS weekday,
    SUM(tickets) AS tickets,
    ROUND(AVG(tickets), 1) AS avg_tickets_per_day
FROM daily
GROUP BY day_of_week
ORDER BY day_of_week;
