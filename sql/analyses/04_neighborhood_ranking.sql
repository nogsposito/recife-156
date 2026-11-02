-- title: Bairros com mais chamados
-- question: Onde a demanda se concentra e qual a posição de cada bairro dentro da sua RPA?
SELECT
    RANK() OVER (ORDER BY COUNT(*) DESC) AS city_rank,
    n.neighborhood_name,
    n.rpa,
    RANK() OVER (PARTITION BY n.rpa ORDER BY COUNT(*) DESC) AS rank_in_rpa,
    COUNT(*) AS tickets,
    ROUND(100.0 * AVG((t.status = 'ATENDIDA')::int), 1) AS pct_resolved
FROM fact_tickets AS t
JOIN dim_neighborhood AS n USING (neighborhood_id)
GROUP BY n.neighborhood_name, n.rpa
ORDER BY tickets DESC
LIMIT 15;
