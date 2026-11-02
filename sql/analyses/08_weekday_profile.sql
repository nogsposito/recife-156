-- title: Chamados por dia da semana
-- question: Em que dias a central recebe mais demandas?
SELECT
    EXTRACT(ISODOW FROM opened_on)::int AS weekday_number,
    (ARRAY['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'])
        [EXTRACT(ISODOW FROM opened_on)::int] AS weekday,
    COUNT(*) AS tickets,
    ROUND(COUNT(*)::numeric / COUNT(DISTINCT opened_on), 1) AS avg_tickets_per_day
FROM tickets
GROUP BY 1, 2
ORDER BY 1;
