# Resultados da avaliação — 2026-11-16 03:54

Modelo de geração: `llama3.2:3b` · embeddings: `nomic-embed-text` · 35 perguntas (gabarito derivado do grafo-gabarito por `scripts/gerar_perguntas.py`).

## Todas com resposta

| Métrica | GraphRAG híbrido | Somente vetorial |
|---|---|---|
| n | 29 | 29 |
| cobertura_contexto | 0.98 | 0.91 |
| fonte_recuperada | 1.00 | 1.00 |
| cobertura_resposta | 0.89 | 0.76 |
| precisao_entidades | 0.71 | 0.60 |
| exatas | 0.59 | 0.41 |
| com_entidade_nao_esperada | 0.34 | 0.55 |
| citacoes_validas | 0.99 | 0.48 |
| sem_citacao | 0.00 | 0.00 |
| segundos | 43.37 | 35.80 |

## 1 salto

| Métrica | GraphRAG híbrido | Somente vetorial |
|---|---|---|
| n | 20 | 20 |
| cobertura_contexto | 1.00 | 0.93 |
| fonte_recuperada | 1.00 | 1.00 |
| cobertura_resposta | 0.95 | 0.86 |
| precisao_entidades | 0.75 | 0.75 |
| exatas | 0.75 | 0.55 |
| com_entidade_nao_esperada | 0.25 | 0.40 |
| citacoes_validas | 0.98 | 0.46 |
| sem_citacao | 0.00 | 0.00 |
| segundos | 43.51 | 25.00 |

## 2 saltos

| Métrica | GraphRAG híbrido | Somente vetorial |
|---|---|---|
| n | 5 | 5 |
| cobertura_contexto | 0.90 | 0.90 |
| fonte_recuperada | 1.00 | 1.00 |
| cobertura_resposta | 0.80 | 0.70 |
| precisao_entidades | 0.53 | 0.30 |
| exatas | 0.40 | 0.20 |
| com_entidade_nao_esperada | 0.60 | 0.80 |
| citacoes_validas | 1.00 | 0.38 |
| sem_citacao | 0.00 | 0.00 |
| segundos | 34.36 | 34.86 |

## 3+ saltos

| Métrica | GraphRAG híbrido | Somente vetorial |
|---|---|---|
| n | 4 | 4 |
| cobertura_contexto | 1.00 | 0.77 |
| fonte_recuperada | 1.00 | 1.00 |
| cobertura_resposta | 0.72 | 0.35 |
| precisao_entidades | 0.76 | 0.36 |
| exatas | 0.00 | 0.00 |
| com_entidade_nao_esperada | 0.50 | 1.00 |
| citacoes_validas | 1.00 | 0.89 |
| sem_citacao | 0.00 | 0.00 |
| segundos | 53.90 | 90.97 |

## Sem resposta

| Métrica | GraphRAG híbrido | Somente vetorial |
|---|---|---|
| n | 6 | 6 |
| precisao_entidades | 0.00 | 0.00 |
| com_entidade_nao_esperada | 0.17 | 0.17 |
| abstencao_correta | 1.00 | 1.00 |
| citacoes_validas | 1.00 | 1.00 |
| sem_citacao | 0.83 | 0.67 |
| segundos | 32.18 | 20.55 |

Reavaliadas depois de falha de infraestrutura na execução original (2026-11-16 03:44): q07 (vector_only), q14 (vector_only), q21 (vector_only), q28 (vector_only), q22 (graphrag), q35 (graphrag).

Definições das métricas no cabeçalho de `evaluate.py`. As respostas completas estão em `avaliacao.json`.
