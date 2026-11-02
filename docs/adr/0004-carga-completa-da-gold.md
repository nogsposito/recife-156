# ADR 0004: Ingestão incremental, carga completa da gold

Status: aceito

## Contexto

A ingestão precisa ser idempotente (rodar duas vezes dá o mesmo resultado) e incremental (não reprocessar o que não mudou). Mas os dados do 156 não têm identificador de chamado, e o mesmo chamado aparece em vários arquivos anuais com situações diferentes. Saber qual versão vale depende de olhar todos os anos juntos.

## Decisão

- Ingestão incremental até a bronze: o manifesto guarda, por arquivo, a versão publicada no portal e o hash do conteúdo. Um ano só é baixado e reescrito quando a versão muda, e só é regravado na bronze quando o conteúdo também muda.
- Silver e gold recalculadas a cada execução, a partir de toda a bronze. A gold é recriada em uma única transação, com os índices construídos depois do `COPY`.

## Alternativas consideradas

- Carga incremental da gold com `UPSERT`: exigiria uma chave estável por chamado, que os dados não têm. A deduplicação por chave composta mudaria a identidade de um chamado de uma execução para outra.

## Consequências

- O resultado é determinístico: a mesma bronze sempre gera a mesma gold, e uma falha no meio da carga deixa a gold anterior intacta.
- O caro (download) é incremental; o barato (recalcular cerca de 200 mil linhas, menos de um minuto) é completo.
- Com muitos anos a mais, a gold precisaria de carga incremental por partição, e a deduplicação teria de ficar restrita aos anos vizinhos.
