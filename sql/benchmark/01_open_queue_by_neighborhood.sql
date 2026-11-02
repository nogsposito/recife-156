-- title: Fila em aberto de um bairro, dos chamados mais antigos para os mais novos
-- The operational drill-down: what is waiting in Boa Viagem, oldest first.
SELECT t.ticket_id, s.service_name, t.opened_on, t.status
FROM fact_tickets AS t
JOIN dim_service AS s USING (service_code)
WHERE t.is_open
  AND t.neighborhood_id = (
      SELECT neighborhood_id FROM dim_neighborhood WHERE neighborhood_name = 'BOA VIAGEM'
  )
ORDER BY t.opened_on
LIMIT 50
