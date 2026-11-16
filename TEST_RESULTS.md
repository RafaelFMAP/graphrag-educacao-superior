# Resultados dos testes — 16/11/2026 (America/Sao_Paulo)

Ambiente desta rodada: macOS (Apple Silicon) com Docker Engine 29.5.3 e 8 GiB de memória para o Docker; Python 3.12 local e nas imagens Linux; Neo4j 5.26 Community com GDS 2.13.15; Ollama com `llama3.2:3b` e `nomic-embed-text` em CPU.

| Verificação | Resultado |
|---|---|
| Testes unitários (`python -m pytest -q`) | 75/75 passaram |
| `docker compose config -q` e `docker compose build` | Passaram |
| Inicialização completa do Compose (modelos, plugin GDS, seed) | Passou: 75 entidades, 167 relações, 3 documentos e 23 trechos; PageRank e Leiden (9 comunidades, modularidade 0,49) gravados |
| `smoke.py --llm` | Passou: índices, busca textual e vetorial, cadeias multi-hop, GDS, recusa de escrita na transação de leitura, procedência, consulta pela interface (AppTest), Text2Cypher, citações e confiança |
| Ingestão real com LLM e resolução de entidades | `ppc-2022.md` reingerido: 0 entidades duplicadas (75 → 75), nenhum nó com rótulo misturado |
| Avaliação GraphRAG x baseline vetorial | Ver `docs/resultados/avaliacao.md` (70 execuções válidas) |
| Avaliação da extração | Ver `docs/resultados/extracao.md` |

## Resultados principais

| Métrica (29 perguntas com resposta) | GraphRAG híbrido | Somente vetorial |
|---|---|---|
| Cobertura da resposta | 0,89 | 0,76 |
| Cobertura da resposta, 3+ saltos | 0,72 | 0,35 |
| Respostas exatas | 0,59 | 0,41 |
| Respostas com entidade não esperada | 0,34 | 0,55 |
| Citações válidas | 0,99 | 0,48 |
| Abstenção correta (6 perguntas sem resposta) | 6/6 | 6/6 |

Extração (NER/RE com `llama3.2:3b`): entidades com F1 0,73 (precisão 0,86); relações com precisão 0,53, que sobe para 0,80 com a assinatura de tipos, mas revocação baixa (0,12).

## Problemas encontrados e corrigidos nesta rodada

- Com 8 GiB para o Docker, o servidor do modelo foi encerrado por falta de memória (SIGKILL) em 6 de 70 respostas da primeira avaliação. O Compose passou a limitar a memória do Neo4j e a usar `OLLAMA_NUM_PARALLEL=1`; a avaliação repete chamadas que falham por infraestrutura e as exclui das médias se continuarem falhando. As 6 execuções foram refeitas com sucesso.
- Text2Cypher: `Query(timeout)` não funciona dentro de `execute_read`; trocado por `unit_of_work`.
- Caminho mínimo: erro interno do Neo4j ao fatiar `nodes(p)[1..-1]` dentro de `shortestPath`; consulta reescrita.
- Resolução de entidades: ordinais não eram reconhecidos como numerais (`7º período` fundido com `6º período`).
- Extração: limite de tokens (`num_predict`) contra geração sem fim no modo JSON estruturado.

## Limites

Estes testes confirmam o funcionamento técnico e medem a qualidade num corpus sintético pequeno; não substituem a revisão humana das relações extraídas nem uma avaliação com documentos reais. As dependências usam faixas de versões e o Ollama usa `latest`; instalações futuras podem resolver versões diferentes. Os modelos e imagens são baixados durante a execução.

Referência para a ordem de inicialização: https://docs.docker.com/compose/how-tos/startup-order/
