# Resultados do NLP

Gerado por `make nlp` ([src/nlp/service_text.py](../src/nlp/service_text.py)). O raciocínio, a matriz de confusão e os exemplos estão no notebook [05_service_text.ipynb](../notebooks/05_service_text.ipynb).

A tarefa: prever o grupo de serviço de uma descrição usada entre 2012 e 2023, aprendendo só com as descrições de 2024 e 2025. O F1 macro dá o mesmo peso a cada grupo; o ponderado pesa pelo número de descrições de cada grupo.

<!-- nlp:start -->
Treino: 94 descrições de 2024 e 2025. Teste: 77 descrições de 2012 a 2023 que não existem nos arquivos atuais.

| Texto do teste | Método | Acurácia | Chamados no grupo certo | F1 macro | F1 ponderado |
|---|---|---|---|---|---|
| original | Caracteres (TF-IDF) + regressão logística | 0,779 | 0,974 | 0,620 | 0,771 |
| original | Embeddings (transformer) + regressão logística | 0,597 | 0,907 | 0,447 | 0,629 |
| original | Embeddings: serviço atual mais parecido | 0,675 | 0,598 | 0,499 | 0,680 |
| com reparo | Caracteres (TF-IDF) + regressão logística | 0,766 | 0,973 | 0,614 | 0,754 |
| com reparo | Embeddings (transformer) + regressão logística | 0,597 | 0,907 | 0,447 | 0,629 |
| com reparo | Embeddings: serviço atual mais parecido | 0,688 | 0,941 | 0,507 | 0,697 |
<!-- nlp:end -->

O de-para sugerido, com o serviço atual mais parecido para cada descrição antiga e a similaridade entre as duas, está em [service_mapping.csv](service_mapping.csv).
