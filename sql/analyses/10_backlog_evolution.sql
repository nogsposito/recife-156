-- title: Evolução da fila em aberto
-- question: A fila está crescendo ou diminuindo mês a mês?
-- Counts only tickets opened since the start of the period, so the queue starts at zero.
WITH opened AS (
    SELECT DATE_TRUNC('month', opened_on)::date AS month, COUNT(*) AS opened
    FROM fact_tickets
    GROUP BY 1
),
resolved AS (
    SELECT DATE_TRUNC('month', status_updated_on)::date AS month, COUNT(*) AS resolved
    FROM fact_tickets
    WHERE NOT is_open
    GROUP BY 1
),
monthly AS (
    SELECT o.month, o.opened, COALESCE(r.resolved, 0) AS resolved
    FROM opened AS o
    LEFT JOIN resolved AS r USING (month)
)
SELECT
    month,
    opened,
    resolved,
    opened - resolved AS net_change,
    SUM(opened - resolved) OVER (ORDER BY month) AS open_at_month_end,
    ROUND(
        AVG(opened - resolved) OVER (ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
    ) AS net_change_3m_avg
FROM monthly
ORDER BY month;
