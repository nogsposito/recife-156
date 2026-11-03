# Resultados do modelo

Gerado por `make train` ([src/ml/train.py](../src/ml/train.py)). O raciocínio, os gráficos e a análise de erros estão no notebook [04_resolution_model.ipynb](../notebooks/04_resolution_model.ipynb).

O alerta é a previsão de que o chamado não será atendido em até 30 dias (chance prevista abaixo de 50%). Precisão do alerta: dos chamados apontados, quantos de fato passaram de 30 dias. Recall do alerta: dos que passaram de 30 dias, quantos foram apontados. Brier: erro quadrático médio da probabilidade (menor é melhor).

<!-- ml:start -->
Treino: chamados abertos até 31/05/2025 (146.062 chamados, 65,7% atendidos em até 30 dias).
Teste: chamados abertos de 01/07/2025 a 01/12/2025 (43.670 chamados, 66,7% atendidos em até 30 dias).

| Modelo | AUC | Brier | Acurácia | Precisão do alerta | Recall do alerta |
|---|---|---|---|---|---|
| Taxa geral do treino | 0,500 | 0,222 | 66,7% | 0,0% | 0,0% |
| Histórico do serviço | 0,954 | 0,073 | 89,8% | 83,4% | 86,8% |
| Gradient boosting | 0,960 | 0,067 | 91,2% | 89,2% | 83,6% |

| Variável | Queda da AUC ao embaralhar |
|---|---|
| `service_name` | 0,4582 |
| `neighborhood_name` | 0,0125 |
| `service_demand_7d` | 0,0015 |
| `group_name` | 0,0008 |
| `neighborhood_demand_30d` | 0,0004 |
| `rpa` | 0,0000 |
| `day_of_week` | 0,0000 |
| `is_weekend` | 0,0000 |
| `month` | -0,0003 |
| `rain_3d_mm` | -0,0004 |
<!-- ml:end -->
