-- title: Evolução mensal de chamados
-- question: A demanda está crescendo? Como cada mês se compara ao mesmo mês do ano anterior?
WITH monthly AS (
    SELECT DATE_TRUNC('month', opened_on)::date AS month, COUNT(*) AS tickets
    FROM tickets
    GROUP BY 1
)
SELECT
    month,
    tickets,
    LAG(tickets, 12) OVER (ORDER BY month) AS tickets_last_year,
    ROUND(
        100.0 * (tickets - LAG(tickets, 12) OVER (ORDER BY month))
        / NULLIF(LAG(tickets, 12) OVER (ORDER BY month), 0),
        1
    ) AS yoy_change_pct
FROM monthly
ORDER BY month;
