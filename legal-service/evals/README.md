# Avaliação - Legal Service

Este diretório contém scripts e datasets para avaliar a qualidade do `legal-service`.

## Arquivos

- `eval_retrieval_dataset.csv`: Dataset com exemplos de validação, incluindo `question`, `ground_truth` (arquivos esperados), e `expected_decision`.
- `evaluate_retrieval.py`: Script Python que avalia **apenas o retrieval** (busca de documentos), calculando precision e recall baseados nos **arquivos** retornados vs. ground truth.
- `evaluate_generation.py`: Script Python que avalia **a geração completa** (decision + severity), comparando as decisões geradas pelo agente com as esperadas do dataset.

## Avaliação de Retrieval

### Pré-requisitos

1. **Weaviate rodando**: O Weaviate precisa estar acessível (via Docker ou localmente).
2. **Variáveis de ambiente**: Configure `WEAVIATE_URL` e `OPENAI_API_KEY` (para embeddings).
3. **Dependências**: Instale as dependências do `legal-service` (o script usa os mesmos módulos).

### Execução local (fora do Docker)

```bash
cd legal-service

# Certifique-se de que o Weaviate está acessível em localhost:8080
# (ou ajuste WEAVIATE_URL no ambiente)

python3 evals/evaluate_retrieval.py \
  --dataset evals/eval_retrieval_dataset.csv \
  --weaviate-url http://localhost:8080 \
  --output evals/retrieval_results.json
```

### Execução via Docker

Se o Weaviate estiver rodando no Docker Compose, você pode executar o script dentro de um container temporário:

```bash
# Na raiz do projeto
docker-compose run --rm legal-service python3 /app/evals/evaluate_retrieval.py \
  --dataset /app/evals/eval_retrieval_dataset.csv \
  --weaviate-url http://weaviate:8080 \
  --output /app/evals/retrieval_results.json
```

Ou, se preferir executar localmente mas apontando para o Weaviate no Docker:

```bash
cd legal-service
WEAVIATE_URL=http://localhost:8080 python3 evals/evaluate_retrieval.py
```

## Métricas calculadas

O script calcula **precision e recall por arquivo**:

- **Precision**: Dos arquivos retornados pelo retriever, quantos estão no ground truth?
  - `precision = |retrieved_files ∩ ground_truth_files| / |retrieved_files|`
  
- **Recall**: Dos arquivos esperados (ground truth), quantos foram retornados?
  - `recall = |retrieved_files ∩ ground_truth_files| / |ground_truth_files|`

- **F1**: Média harmônica de precision e recall.

### Métricas agregadas

- **Macro-average**: Média aritmética das métricas de todos os exemplos.
- O script também mostra os **top 5 piores** e **top 5 melhores** casos.

## Formato do dataset

O CSV deve ter as seguintes colunas (separadas por `;`):

- `channel`: Canal de comunicação (SMS, PUSH, etc.)
- `content`: Conteúdo da mensagem a ser validada
- `question`: Query completa para o retriever (formato: `VALIDATE_COMMUNICATION para CHANNEL: content`)
- `ground_truth`: Arquivos esperados, separados por `|` (ex: `file1.pdf|file2.pdf`)
- `expected_decision`: Decisão esperada (APROVADO/REPROVADO/etc.) - não usado na avaliação de retrieval

## Exemplo de saída

```
================================================================================
RESUMO DA AVALIAÇÃO DE RETRIEVAL
================================================================================

Total de exemplos: 40
Exemplos processados com sucesso: 40

Métricas agregadas (macro-average):
  Precision: 0.8234
  Recall:    0.7567
  F1:        0.7889

================================================================================

Top 5 piores casos (menor F1):
  [12] F1=0.000 | P=0.000 R=0.000
      Question: VALIDATE_COMMUNICATION para SMS: ORQESTRA: ÚLTIMA CHANCE!!!...
      Expected: ['orqestra-guidelines-comunicacao-SMS_v1.pdf', ...]
      Retrieved: ['outro-arquivo.pdf']

...
```

## Interpretação dos resultados

- **Precision alta, Recall baixo**: O retriever está retornando arquivos relevantes, mas está perdendo alguns arquivos importantes.
  - **Ação**: Aumentar `limit` no `config/models.yaml` ou ajustar `alpha` (peso do hybrid search).

- **Recall alto, Precision baixo**: O retriever está retornando muitos arquivos, mas muitos são irrelevantes.
  - **Ação**: Reduzir `limit` ou melhorar a qualidade dos embeddings/indexação.

- **Ambos baixos**: Problema mais grave na indexação ou na query.
  - **Ação**: Revisar como os documentos foram indexados, verificar se os metadados (`file_name`, `source_file`) estão corretos.

## Notas

- O script usa o mesmo `HybridWeaviateRetriever` e configurações (`limit`, `alpha`) do serviço em produção.
- A avaliação é **file-level**, não text-level. Ou seja, medimos se os **arquivos certos** foram retornados, não se o conteúdo específico dentro deles está correto.

---

## Avaliação de Geração

### Pré-requisitos

1. **Weaviate rodando**: O Weaviate precisa estar acessível.
2. **Variáveis de ambiente**: Configure `WEAVIATE_URL`, `OPENAI_API_KEY` (para embeddings), e `MARITACA_API_KEY` ou `OPENAI_API_KEY` (para o LLM).
3. **Dependências**: Instale as dependências do `legal-service`.

### Execução local

```bash
cd legal-service

# Certifique-se de que o Weaviate e Redis estão acessíveis
export WEAVIATE_URL=http://localhost:8080
export OPENAI_API_KEY=sua_key_aqui
export MARITACA_API_KEY=sua_key_aqui  # Opcional, usa OpenAI como fallback

python3 evals/evaluate_generation.py \
  --dataset evals/eval_retrieval_dataset.csv \
  --weaviate-url http://localhost:8080 \
  --output evals/generation_results.json
```

### Execução via Docker

```bash
# Na raiz do projeto
docker-compose run --rm legal-service python3 /app/evals/evaluate_generation.py \
  --dataset /app/evals/eval_retrieval_dataset.csv \
  --weaviate-url http://weaviate:8080 \
  --output /app/evals/generation_results.json
```

### Métricas calculadas

O script avalia a qualidade das **decisões geradas** pelo agente completo (retrieval + LLM):

- **Accuracy (Decision)**: Percentual de exemplos onde `decision` (APROVADO/REPROVADO) está correta.
- **Accuracy (Severity)**: Percentual de exemplos onde `severity` (BLOCKER/WARNING/INFO) está correta.
- **Accuracy (Ambos)**: Percentual de exemplos onde tanto `decision` quanto `severity` estão corretos.
- **Precision/Recall/F1 por classe**: Métricas detalhadas para cada valor de `decision` e `severity`.
- **Matriz de confusão**: Mostra onde o modelo está errando (ex: classificando como APROVADO quando deveria ser REPROVADO).

### Mapeamento de expected_decision

O CSV tem valores como `APROVADO`, `BLOCKER`, `WARNING`. O script mapeia assim:

- `APROVADO` → `decision=APROVADO, severity=INFO`
- `BLOCKER` → `decision=REPROVADO, severity=BLOCKER`
- `WARNING` → `decision=REPROVADO, severity=WARNING`

### Exemplo de saída

```
================================================================================
RESUMO DA AVALIAÇÃO DE GERAÇÃO
================================================================================

Configuração:
  LLM: sabiazinho-4 (maritaca)
  Embeddings: text-embedding-3-small
  Cache: disabled

Total de exemplos: 40

Accuracy:
  Decision apenas:  0.9250 (92.50%)
  Severity apenas:  0.8750 (87.50%)
  Decision + Severity: 0.8250 (82.50%)

Métricas por Decision:
  APROVADO     | Precision: 0.9000 | Recall: 0.8571 | F1: 0.8780 | Support: 7
  REPROVADO    | Precision: 0.9375 | Recall: 0.9697 | F1: 0.9533 | Support: 33

...
```

### Notas

- Por padrão, o **cache está desabilitado** para garantir uma avaliação justa (sem resultados de execuções anteriores).
- O script usa o mesmo `LegalAgent` e configurações do serviço em produção (mesmo LLM: `sabiazinho-4` ou `gpt-5-nano` fallback).
- A avaliação é **simples**: compara apenas se a decisão/severity está correta, não avalia a qualidade do `summary` (justificativa).
