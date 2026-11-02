# Análises dos chamados do 156

Relatório gerado por `make report` ([src/analysis/report.py](../src/analysis/report.py)) a partir das consultas em [sql/analyses](../sql/analyses). Todos os números vêm da execução dessas consultas sobre o banco carregado.

Recorte: 204.329 chamados abertos entre 01/01/2024 e 31/12/2025, com a situação conhecida até 31/12/2025.

## Hipóteses de negócio

### H1. Poucos serviços concentram a maior parte da demanda

Hipótese: os 10 serviços mais pedidos somam pelo menos 70% dos chamados.

Por que importa: se a demanda é concentrada, prevenir ou automatizar poucos serviços alivia a central de forma desproporcional.

Como foi testada: participação acumulada dos serviços ordenados por volume ([02_service_concentration.sql](../sql/analyses/02_service_concentration.sql)).

Resultado: Confirmada. Os 10 primeiros, de 108 serviços, somam 78,0% dos chamados. Só "MANUTENCAO EM LAMPADA APAGADA" (ILUMINACAO PUBLICA) responde por 35,6%: é o pedido em que prevenção ou um canal automático teria o maior efeito isolado sobre o volume da central.

### H2. O tempo de atendimento é parecido entre as regiões da cidade

Hipótese: dentro de um mesmo grupo de serviço, a região (RPA) mais lenta não leva mais que o dobro do tempo da mais rápida, considerando a mediana de dias até o atendimento.

Por que importa: se a espera depende da região e não só do tipo de serviço, há um problema de capacidade ou de contrato regional que a gestão pode atacar diretamente.

Como foi testada: mediana de dias até o atendimento por grupo e RPA, nos quatro maiores grupos ([06_resolution_time_by_rpa.sql](../sql/analyses/06_resolution_time_by_rpa.sql)). Um grupo conta como desigual quando a RPA mais lenta leva mais que o dobro da mais rápida e a diferença passa de 7 dias.

| Grupo | RPA mais rápida | RPA mais lenta | Lenta / rápida |
|---|---|---|---|
| DRENAGEM | RPA 3 (1 d) | RPA 6 (177 d) | 177,0x |
| ARBORIZACAO | RPA 3 (13 d) | RPA 6 (35 d) | 2,7x |
| ILUMINACAO PUBLICA | RPA 1 (1 d) | RPA 4 (2 d) | 2,0x |
| LIMPEZA URBANA | RPA 1 (9 d) | RPA 5 (14 d) | 1,6x |

Resultado: Refutada para DRENAGEM e ARBORIZACAO; vale para ILUMINACAO PUBLICA e LIMPEZA URBANA.

Limitações: a mediana considera só chamados já atendidos, e a mistura de serviços dentro de um grupo pode variar entre regiões. A data de atendimento é a da última mudança de situação registrada, que pode refletir a prática de registro de cada equipe, e não só o trabalho em campo.

## Gráficos

![Chamados abertos por mês](img/monthly_trend.png)

![Chamados por grupo de serviço](img/volume_by_group.png)

![Mediana de dias até o atendimento por região](img/resolution_by_rpa.png)

No mapa de calor a cor segue escala logarítmica, porque os valores vão de 1 dia a vários meses.

## Consultas

### 1. Volume por grupo de serviço

Pergunta: Quais áreas da Emlurb recebem mais demandas?

Consulta: [01_volume_by_group.sql](../sql/analyses/01_volume_by_group.sql)

| Grupo | Chamados | % do total |
|---|---|---|
| ILUMINACAO PUBLICA | 94.001 | 46,0 |
| LIMPEZA URBANA | 40.463 | 19,8 |
| ARBORIZACAO | 22.185 | 10,9 |
| DRENAGEM | 17.985 | 8,8 |
| PAVIMENTACAO | 8.566 | 4,2 |
| DENUNCIAS | 4.179 | 2,0 |
| MANUT. URBANA | 2.601 | 1,3 |
| FISCALIZACAO URBANA | 2.149 | 1,1 |
| PRACAS | 2.016 | 1,0 |
| COLETA URBANA | 1.993 | 1,0 |
| ESCADARIA | 1.730 | 0,8 |
| MACRODRENAGEM | 1.482 | 0,7 |
| PROJETOS | 1.385 | 0,7 |
| POSTE | 1.314 | 0,6 |
| ACAO EDUCATIVA | 753 | 0,4 |

Mostrando 15 de 24 linhas.

ILUMINACAO PUBLICA responde por 46,0% dos chamados, e os três maiores grupos somam 76,7%.

### 2. Concentração da demanda por serviço

Pergunta: Quantos serviços respondem pela maior parte dos chamados?

Consulta: [02_service_concentration.sql](../sql/analyses/02_service_concentration.sql)

| Posição | Serviço | Grupo | Chamados | % do total | % acumulado |
|---|---|---|---|---|---|
| 1 | MANUTENCAO EM LAMPADA APAGADA | ILUMINACAO PUBLICA | 72.674 | 35,6 | 35,6 |
| 2 | REMOCAO DE ENTULHOS | LIMPEZA URBANA | 23.374 | 11,4 | 47,0 |
| 3 | ACENDER CIRCUITO | ILUMINACAO PUBLICA | 14.626 | 7,2 | 54,2 |
| 4 | VISTORIA DE ARVORES | ARBORIZACAO | 13.900 | 6,8 | 61,0 |
| 5 | CAPINACAO EM VIA PAVIMENTADA | LIMPEZA URBANA | 9.861 | 4,8 | 65,8 |
| 6 | LIMPEZA DE GALERIAS E VALETAS | DRENAGEM | 7.469 | 3,7 | 69,4 |
| 7 | PODA DE ARVORES | ARBORIZACAO | 6.189 | 3,0 | 72,5 |
| 8 | REPOSICAO TAMPA DE POCO, GALERIAS,MEIO FIO E PRE-MOLDADOS | DRENAGEM | 3.959 | 1,9 | 74,4 |
| 9 | CAPINACAO EM VIA NAO PAVIMENTADA | LIMPEZA URBANA | 3.927 | 1,9 | 76,3 |
| 10 | DENUNCIA DE ARBOVIROSES (DENGUE, CHIKUNGUNYA, ZIKA VIRUS) | DENUNCIAS | 3.302 | 1,6 | 78,0 |
| 11 | RECUP.DE CANALETAS DE DRENAGEM | DRENAGEM | 2.802 | 1,4 | 79,3 |
| 12 | RECUPERACAO DE PAVIMENTO PARALELEPIPEDO | PAVIMENTACAO | 2.747 | 1,3 | 80,7 |
| 13 | OPERACAO TAPA-BURACO | PAVIMENTACAO | 2.045 | 1,0 | 81,7 |
| 14 | LUMINARIAS | ILUMINACAO PUBLICA | 2.025 | 1,0 | 82,7 |
| 15 | REGULARIZAR COLETA DOMICILIAR | COLETA URBANA | 1.993 | 1,0 | 83,6 |

Mostrando 15 de 108 linhas.

Dos 108 serviços com chamados no período, 12 concentram 80% do volume. Detalhes na hipótese H1.

### 3. Evolução mensal de chamados

Pergunta: A demanda está crescendo? Como cada mês se compara ao mesmo mês do ano anterior?

Consulta: [03_monthly_trend.sql](../sql/analyses/03_monthly_trend.sql)

| Mês | Chamados | Mesmo mês do ano anterior | Variação anual (%) |
|---|---|---|---|
| 01/2024 | 8.706 | - | - |
| 02/2024 | 9.176 | - | - |
| 03/2024 | 8.905 | - | - |
| 04/2024 | 11.064 | - | - |
| 05/2024 | 9.446 | - | - |
| 06/2024 | 8.162 | - | - |
| 07/2024 | 8.100 | - | - |
| 08/2024 | 7.048 | - | - |
| 09/2024 | 7.377 | - | - |
| 10/2024 | 7.384 | - | - |
| 11/2024 | 6.747 | - | - |
| 12/2024 | 7.159 | - | - |
| 01/2025 | 9.588 | 8.706 | 10,1 |
| 02/2025 | 8.956 | 9.176 | -2,4 |
| 03/2025 | 9.338 | 8.905 | 4,9 |
| 04/2025 | 8.828 | 11.064 | -20,2 |
| 05/2025 | 10.016 | 9.446 | 6,0 |
| 06/2025 | 8.594 | 8.162 | 5,3 |
| 07/2025 | 9.586 | 8.100 | 18,3 |
| 08/2025 | 9.155 | 7.048 | 29,9 |
| 09/2025 | 8.896 | 7.377 | 20,6 |
| 10/2025 | 8.517 | 7.384 | 15,3 |
| 11/2025 | 7.261 | 6.747 | 7,6 |
| 12/2025 | 6.320 | 7.159 | -11,7 |

Em 2025 foram abertos 105.055 chamados, 5,8% a mais que em 2024. O mês de maior volume foi abril de 2024 (11.064 chamados).

### 4. Bairros com mais chamados

Pergunta: Onde a demanda se concentra e qual a posição de cada bairro dentro da sua RPA?

Consulta: [04_neighborhood_ranking.sql](../sql/analyses/04_neighborhood_ranking.sql)

| Posição na cidade | Bairro | RPA | Posição na RPA | Chamados | % atendidos |
|---|---|---|---|---|---|
| 1 | BOA VIAGEM | 6 | 1 | 12.779 | 76,2 |
| 2 | SANTO AMARO | 1 | 1 | 8.411 | 82,0 |
| 3 | IMBIRIBEIRA | 6 | 2 | 7.468 | 73,4 |
| 4 | COHAB IBURA DE CIMA | 6 | 3 | 7.272 | 74,0 |
| 5 | VARZEA | 4 | 1 | 7.114 | 74,4 |
| 6 | IPUTINGA | 4 | 2 | 7.019 | 75,6 |
| 7 | CORDEIRO | 4 | 3 | 6.590 | 72,0 |
| 8 | AFOGADOS | 5 | 1 | 5.715 | 71,2 |
| 9 | IBURA | 6 | 4 | 5.347 | 73,4 |
| 10 | BOA VISTA | 1 | 2 | 5.164 | 89,0 |
| 11 | AREIAS | 5 | 2 | 4.898 | 76,4 |
| 12 | CAMPO GRANDE | 2 | 1 | 4.596 | 81,8 |
| 13 | PINA | 6 | 5 | 4.361 | 80,0 |
| 14 | CASA AMARELA | 3 | 1 | 4.264 | 74,9 |
| 15 | SAN MARTIN | 5 | 3 | 3.520 | 70,2 |

BOA VIAGEM (RPA 6) lidera com 12.779 chamados. Entre esses bairros, a parcela já atendida vai de 70,2% (SAN MARTIN) a 89,0% (BOA VISTA).

### 5. Tempo de resolução por grupo de serviço

Pergunta: Quanto tempo cada tipo de serviço leva para ser atendido?

Consulta: [05_resolution_time_by_group.sql](../sql/analyses/05_resolution_time_by_group.sql)

| Grupo | Atendidos | Mediana (dias) | P90 (dias) | % em até 7 dias |
|---|---|---|---|---|
| ESCADARIA | 192 | 225 | 449,6 | 1,0 |
| ACAO EDUCATIVA | 303 | 169 | 406,6 | 1,0 |
| MACRODRENAGEM | 226 | 129 | 270,5 | 0,9 |
| DRENAGEM | 4.024 | 47 | 259 | 35,7 |
| PLANEJAMENTO DE LIMPEZA URBANA | 132 | 42,5 | 211,1 | 17,4 |
| PAVIMENTACAO | 1.987 | 31 | 158 | 22,2 |
| PRACAS | 672 | 21 | 322,2 | 4,6 |
| DENUNCIAS | 3.289 | 20 | 46 | 14,4 |
| ARBORIZACAO | 10.547 | 19 | 126 | 23,4 |
| LIMPEZA URBANA | 39.002 | 12 | 118 | 36,8 |
| FISCALIZACAO URBANA | 1.684 | 8 | 50 | 45,2 |
| COLETA SELETIVA | 351 | 8 | 20 | 43,0 |
| COLETA URBANA | 1.942 | 5,5 | 22 | 66,8 |
| ILUMINACAO PUBLICA | 92.258 | 2 | 5 | 94,2 |
| POSTE | 781 | 0 | 27 | 86,2 |
| ILUMINACAO PROVISORIA | 201 | 0 | 0 | 99,0 |

ILUMINACAO PROVISORIA tem mediana de 0 dias, enquanto ESCADARIA leva 225. A conta considera só chamados já atendidos: em grupos com fila grande, o tempo real tende a ser maior.

### 6. Tempo de resolução por região (RPA) nos maiores grupos

Pergunta: Dentro de um mesmo tipo de serviço, alguma região espera mais?

Consulta: [06_resolution_time_by_rpa.sql](../sql/analyses/06_resolution_time_by_rpa.sql)

| Grupo | RPA | Atendidos | Mediana (dias) | P90 (dias) |
|---|---|---|---|---|
| ARBORIZACAO | 1 | 1.214 | 17 | 62 |
| ARBORIZACAO | 2 | 2.282 | 14 | 83 |
| ARBORIZACAO | 3 | 1.614 | 13 | 96,7 |
| ARBORIZACAO | 4 | 2.448 | 28 | 156 |
| ARBORIZACAO | 5 | 1.462 | 32 | 169 |
| ARBORIZACAO | 6 | 1.527 | 35 | 134,4 |
| DRENAGEM | 1 | 485 | 75 | 192,0 |
| DRENAGEM | 2 | 1.386 | 5 | 243,5 |
| DRENAGEM | 3 | 1.253 | 1 | 182 |
| DRENAGEM | 4 | 202 | 159,5 | 293,8 |
| DRENAGEM | 5 | 266 | 155 | 285 |
| DRENAGEM | 6 | 431 | 177 | 280 |
| ILUMINACAO PUBLICA | 1 | 16.570 | 1 | 6 |
| ILUMINACAO PUBLICA | 2 | 9.083 | 1 | 2 |
| ILUMINACAO PUBLICA | 3 | 16.079 | 1 | 2 |

Mostrando 15 de 24 linhas.

Ver hipótese H2 e o mapa de calor na seção de gráficos.

### 7. Fila de chamados em aberto por idade

Pergunta: Quanto da fila está parada há muito tempo, e em quais serviços?

Consulta: [07_backlog_aging.sql](../sql/analyses/07_backlog_aging.sql)

| Grupo | Em aberto | Até 30 dias | 31 a 180 dias | Mais de 180 dias | % acima de 180 dias |
|---|---|---|---|---|---|
| DRENAGEM | 13.961 | 424 | 3.017 | 10.520 | 75,4 |
| ARBORIZACAO | 11.638 | 369 | 2.370 | 8.899 | 76,5 |
| PAVIMENTACAO | 6.579 | 205 | 2.302 | 4.072 | 61,9 |
| MANUT. URBANA | 2.585 | 93 | 641 | 1.851 | 71,6 |
| ILUMINACAO PUBLICA | 1.743 | 164 | 785 | 794 | 45,6 |
| ESCADARIA | 1.538 | 23 | 246 | 1.269 | 82,5 |
| LIMPEZA URBANA | 1.461 | 324 | 613 | 524 | 35,9 |
| PROJETOS | 1.348 | 56 | 464 | 828 | 61,4 |
| PRACAS | 1.344 | 39 | 338 | 967 | 71,9 |
| MACRODRENAGEM | 1.256 | 47 | 226 | 983 | 78,3 |

Nos 10 grupos com maior fila, 43.453 chamados seguiam em aberto no fim do recorte, 70,7% deles há mais de 180 dias. DRENAGEM sozinho tem 13.961.

### 8. Chamados por dia da semana

Pergunta: Em que dias a central recebe mais demandas?

Consulta: [08_weekday_profile.sql](../sql/analyses/08_weekday_profile.sql)

| Nº | Dia | Chamados | Média por dia |
|---|---|---|---|
| 1 | Segunda | 34.903 | 332,4 |
| 2 | Terça | 40.119 | 382,1 |
| 3 | Quarta | 38.102 | 362,9 |
| 4 | Quinta | 37.131 | 357 |
| 5 | Sexta | 33.080 | 318,1 |
| 6 | Sábado | 11.378 | 109,4 |
| 7 | Domingo | 9.616 | 92,5 |

Dias úteis concentram 89,7% dos chamados, o que sugere dimensionar a equipe de triagem pelo calendário útil.
