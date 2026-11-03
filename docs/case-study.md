# Estudo de caso: o que 200 mil chamados do 156 dizem sobre os serviços urbanos do Recife

## Em uma frase

Cruzando os chamados abertos dos dados abertos da prefeitura com a chuva diária da cidade, o projeto mostra que o 156 recebe sobretudo pedidos de iluminação, que são resolvidos em dias, e que o problema real está em drenagem e arborização: ali a espera depende da região da cidade, a fila cresce todo mês e a chuva forte empurra a demanda para cima.

## O problema

O 156 é a central em que moradores do Recife pedem conserto de lâmpada, poda de árvore, limpeza de galeria, tapa-buraco. São mais de 100 mil pedidos por ano. A prefeitura publica esses chamados como dados abertos, mas em CSVs anuais, sem número de protocolo, com formatos que mudam entre anos e com o mesmo pedido repetido em arquivos diferentes.

As perguntas de gestão são simples de enunciar e difíceis de responder com esses arquivos: onde está a demanda, quanto tempo cada serviço leva, se alguma região espera mais, quanto da fila está parada, se a chuva antecipa picos e quais chamados recém-abertos devem atrasar.

## Os dados e suas armadilhas

Antes de qualquer análise, o primeiro notebook abre os arquivos brutos e registra o que encontra. Quatro descobertas mudaram o projeto:

1. O arquivo de um ano não traz só chamados daquele ano. O de 2025 tem 9.560 chamados abertos antes, alguns desde 2010: ele é uma foto do fim do ano, com todo chamado que mudou de situação.
2. O mesmo chamado aparece em mais de um arquivo, com situações diferentes. Sem protocolo, a solução foi reconhecê-lo pela combinação de serviço, endereço, bairro e data de abertura e manter só a versão mais recente.
3. Até 2023 a codificação era outra (o código 20 era limpeza urbana e virou coleta) e as letras acentuadas foram apagadas na origem ("MANUTENO EM LMPADA APAGADA"). Por isso a análise usa 2024 e 2025.
4. Só uma parte das linhas tem coordenadas, e algumas caem no meio do oceano. As comparações regionais usam bairro e RPA.

## Como foi construído

O projeto cresceu em seis etapas, cada uma deixando um sistema completo e funcionando:

1. Núcleo: ingestão pela API do portal, limpeza, PostgreSQL e consultas SQL, com a limpeza e a análise contadas em notebooks.
2. Segunda fonte e público: clima diário do Open-Meteo e um dashboard Streamlit com uma página para a operação, uma para a gestão e uma para a direção.
3. Engenharia: camadas bronze, silver e gold, ingestão incremental e idempotente, validações de qualidade que bloqueiam a carga, esquema estrela, benchmark de índices e integração contínua.
4. Machine learning: um modelo que prevê, na abertura, se o chamado será atendido em até 30 dias.
5. IA aplicada: NLP sobre as descrições de serviço e um assistente que responde perguntas em português gerando SQL.
6. Acabamento: MongoDB com o dado bruto, documentação e este estudo de caso.

Tudo roda com `docker compose up`: o banco sobe, o pipeline carrega, o modelo treina e o dashboard abre.

## Decisões que fizeram diferença

Tratar cada arquivo anual como uma foto, e não como "os chamados do ano". Essa decisão sozinha evita contar cerca de 3 mil chamados duas vezes e mistura de anos.

Ingestão incremental só até a bronze, gold sempre recalculada. Baixar é o caro; recalcular 200 mil linhas leva menos de um minuto. Sem um identificador estável de chamado, uma carga incremental na gold mudaria a identidade dos chamados entre execuções. Rodar o pipeline duas vezes dá a mesma gold, e o banco registra cada execução e cada validação.

Prever "atendido em até 30 dias" em vez de "quantos dias". Um quarto dos chamados ainda está aberto e não tem tempo de resolução. Um modelo treinado só com os atendidos aprenderia um mundo em que tudo se resolve. Com o alvo binário, um chamado aberto há mais de 30 dias é um "não" conhecido.

Comparar sempre com uma régua honesta. O modelo de 30 dias foi comparado com a taxa histórica de cada serviço, que já acerta muito. O NLP foi comparado com n-gramas de caracteres. Nos dois casos a régua simples ficou perto ou na frente, e isso está dito nos resultados.

Segurança em camadas no assistente. A SQL gerada pelo modelo passa por uma validação (um comando, só leitura, só as tabelas certas), roda com um usuário de banco que só lê, em transação somente leitura e com tempo máximo. Cada camada funciona mesmo que a anterior falhe, e a SQL sempre aparece para quem perguntou.

## O que os dados mostraram

- Poucos serviços concentram a demanda: 10 de 108 somam 78% dos chamados, e "lâmpada apagada" sozinho é 35,6%.
- O tipo de serviço define a espera: iluminação tem mediana de 2 dias; drenagem, 47.
- Em drenagem e arborização a região pesa: no mesmo serviço, as regiões oeste, sudoeste e sul esperam de 155 a 197 dias, contra 35 a 69 nas demais.
- A fila cresce: entre os chamados abertos desde 2024, entrou mais do que saiu em todos os 24 meses, cerca de 1.900 por mês.
- Chuva forte aumenta a demanda, mas não explica a fila: drenagem fica 13% e arborização 20% acima do normal nos dias seguintes a temporais.
- Dá para prever quem vai atrasar, e o serviço é quase tudo: o modelo acerta 89% dos alertas de atraso, contra 83% do histórico do serviço, com ganho concentrado onde a região pesa.
- Doze anos de histórico podem ser recuperados: um de-para semiautomático põe no grupo certo descrições antigas que somam mais de 90% dos chamados.

## O que deu errado no caminho

Uma correção de limpeza criou outro erro. Ao tratar "00" como "sem número", linhas que só ficavam iguais depois da padronização passaram a ser descartadas como duplicadas, e 429 chamados sumiram. A regra certa era considerar duplicada só a linha idêntica no arquivo bruto.

O transformer perdeu para o baseline. Nas descrições de serviço, curtas e com grafias quebradas, n-gramas de caracteres classificaram melhor que embeddings. Os embeddings só ficaram úteis depois de restaurar as palavras quebradas a partir do vocabulário atual, e para outra tarefa: sugerir o serviço equivalente.

Índice não resolve tudo. A consulta mais pesada não melhorou com índice nenhum, porque precisava contar a tabela inteira. O que funcionou foi reescrevê-la para agregar antes de juntar com o calendário, 2,5 vezes mais rápida e com o mesmo resultado.

APIs públicas falham. Uma execução do zero travou por quase duas horas esperando uma resposta e outra caiu num timeout do serviço de clima. As chamadas passaram a tentar de novo com espera crescente, e o pipeline segue com a bronze já baixada quando o portal está fora do ar.

## Aprendizados

- Abrir os dados brutos antes de planejar a análise economiza retrabalho: as quatro armadilhas do início definiram metade das decisões.
- Uma régua simples bem escolhida é o melhor teste de um modelo. Quando ela ganha, isso é um resultado, não um fracasso.
- Separar o caro do barato orienta a arquitetura: incremental onde custa, recalculado onde é rápido e mais seguro.
- Validação de dados e testes valem mais quando pegam o próprio erro de quem escreveu, como no caso das duplicatas.

## Próximos passos

- Revisar o de-para das descrições antigas e estender as análises para 2012 a 2025.
- Trocar a chuva estimada por dados de pluviômetro por bairro (INMET ou APAC).
- Medir o assistente com um conjunto de perguntas e respostas esperadas antes de abrir para uso.
- Publicar o dashboard com o banco hospedado, para ser usado fora da máquina local.
