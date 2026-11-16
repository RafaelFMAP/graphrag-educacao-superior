# Resultados da avaliação — 2026-11-16 02:56

Modelo de geração: `sem LLM` · embeddings: `nomic-embed-text` · 35 perguntas (gabarito derivado do grafo-gabarito por `scripts/gerar_perguntas.py`).

## Todas com resposta

| Métrica | GraphRAG híbrido | Somente vetorial |
|---|---|---|
| n | 29 | 29 |
| cobertura_contexto | 0.98 | 0.91 |
| fonte_recuperada | 1.00 | 1.00 |

## 1 salto

| Métrica | GraphRAG híbrido | Somente vetorial |
|---|---|---|
| n | 20 | 20 |
| cobertura_contexto | 1.00 | 0.93 |
| fonte_recuperada | 1.00 | 1.00 |

## 2 saltos

| Métrica | GraphRAG híbrido | Somente vetorial |
|---|---|---|
| n | 5 | 5 |
| cobertura_contexto | 0.90 | 0.90 |
| fonte_recuperada | 1.00 | 1.00 |

## 3+ saltos

| Métrica | GraphRAG híbrido | Somente vetorial |
|---|---|---|
| n | 4 | 4 |
| cobertura_contexto | 0.98 | 0.77 |
| fonte_recuperada | 1.00 | 1.00 |

## Sem resposta

| Métrica | GraphRAG híbrido | Somente vetorial |
|---|---|---|
| n | 6 | 6 |

Definições das métricas no cabeçalho de `evaluate.py`. As respostas completas estão em `avaliacao.json`.
