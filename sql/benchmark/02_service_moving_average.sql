-- title: Médias móveis de 7 e 28 dias de um serviço no semestre
-- Daily tickets of one service over the calendar (days without tickets count as zero),
-- smoothed with window frames.
WITH daily AS (
    SELECT d.date_key, COUNT(t.ticket_id) AS tickets
    FROM dim_date AS d
    LEFT JOIN fact_tickets AS t
        ON t.opened_on = d.date_key
       AND t.service_code = (
           SELECT service_code
           FROM dim_service
           WHERE service_name = 'LIMPEZA DE GALERIAS E VALETAS'
       )
    WHERE d.date_key BETWEEN DATE '2025-07-01' AND DATE '2025-12-31'
    GROUP BY d.date_key
)
SELECT
    date_key,
    tickets,
    ROUND(AVG(tickets) OVER (ORDER BY date_key ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 1)
        AS moving_avg_7d,
    ROUND(AVG(tickets) OVER (ORDER BY date_key ROWS BETWEEN 27 PRECEDING AND CURRENT ROW), 1)
        AS moving_avg_28d
FROM daily
ORDER BY date_key
