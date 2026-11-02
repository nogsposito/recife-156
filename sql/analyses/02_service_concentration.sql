-- title: Concentração da demanda por serviço
-- question: Quantos serviços respondem pela maior parte dos chamados?
WITH service_volume AS (
    SELECT s.service_name, s.group_name, COUNT(*) AS tickets
    FROM fact_tickets AS t
    JOIN dim_service AS s USING (service_code)
    GROUP BY s.service_name, s.group_name
)
SELECT
    ROW_NUMBER() OVER (ORDER BY tickets DESC) AS position,
    service_name,
    group_name,
    tickets,
    ROUND(100.0 * tickets / SUM(tickets) OVER (), 1) AS pct_total,
    ROUND(
        100.0 * SUM(tickets) OVER (ORDER BY tickets DESC ROWS UNBOUNDED PRECEDING)
        / SUM(tickets) OVER (),
        1
    ) AS cumulative_pct
FROM service_volume
ORDER BY position;
