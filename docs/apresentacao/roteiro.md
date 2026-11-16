# Roteiro da apresentação de defesa

Duração sugerida: **15 minutos de apresentação + 5 de demonstração ao vivo + perguntas**. São 12 slides; a coluna "Quem" divide as falas entre os integrantes. Ajuste conforme o tamanho do grupo (4 a 6 pessoas).

| # | Slide | Conteúdo essencial | Quem | Tempo |
|---|---|---|---|---|
| 1 | Título | Nome do projeto, integrantes, disciplina e docente | Integrante 1 | 0:30 |
| 2 | Problema | LLMs alucinam e falham em perguntas multi-hop ("quais são todos os pré-requisitos de Grafos de Conhecimento?"); a busca vetorial pura não liga entidades distantes | Integrante 1 | 1:00 |
| 3 | Domínio e dados | Educação superior: PPC 2026 (40 disciplinas), PPC 2022 e Regulamento 2026, todos sintéticos; grafo-gabarito com 75 entidades e 167 relações gerado junto com o corpus | Integrante 1 | 1:00 |
| 4 | Arquitetura | Os quatro pilares do enunciado: Text-to-Graph → Neo4j LPG → recuperação híbrida → interface; Docker Compose com Neo4j + GDS, Ollama e Streamlit | Integrante 2 | 1:30 |
| 5 | Modelagem LPG | Diagrama do schema (README); constraints, índices RANGE, fulltext (`brazilian`) e vetoriais; procedência em cada relação; assinatura de tipos | Integrante 2 | 1:30 |
| 6 | Pipeline Text-to-Graph | Extração com JSON estruturado, allowlist e evidência literal; resolução de entidades em cascata e as proteções (`Cálculo I` ≠ `Cálculo II`); métricas de `docs/resultados/extracao.md` | Integrante 3 | 1:30 |
| 7 | Recuperação híbrida | RRF entre vetor e fulltext, ligação de entidades, expansão multi-hop sem hubs, cadeias dirigidas, PageRank, Leiden e caminho mínimo | Integrante 3 | 1:30 |
| 8 | Text2Cypher seguro | Esquema + exemplos → Cypher; validação estática, transação de leitura com timeout, nova tentativa com o erro; mostrar uma consulta recusada | Integrante 4 | 1:00 |
| 9 | Mitigação de alucinações | Evidências numeradas, verificação das citações, abstenção e confiança com sinais explícitos | Integrante 4 | 1:00 |
| 10 | Resultados | Tabela de `docs/resultados/avaliacao.md`: GraphRAG x baseline vetorial por número de saltos, abstenção e citações válidas | Integrante 5 | 2:00 |
| 11 | Limitações e próximos passos | Modelo de 3B em CPU, dados sintéticos, métricas por correspondência de nomes, extração com erros de direção | Integrante 5 | 1:00 |
| 12 | Conclusão | O que o grafo acrescenta (multi-hop, procedência, abstenção) e o que fica para trabalhos futuros | Integrante 6 | 0:30 |

## Demonstração ao vivo (5 minutos)

Antes da defesa, suba o ambiente (`docker compose up -d`) e faça uma pergunta de aquecimento: a primeira chamada ao Ollama carrega o modelo na memória e demora mais.

1. **Pergunta de 1 salto**: *Quais são os pré-requisitos diretos de Projeto Integrador?* Mostrar a resposta com citações, o grafo (estrela na âncora, bordas escuras nas entidades citadas) e a aba **Consultas Cypher** com o Text2Cypher.
2. **Pergunta multi-hop**: *Quais são todos os pré-requisitos, diretos e indiretos, de Grafos de Conhecimento?* Mostrar as cadeias na aba **Evidências numeradas** e repetir no modo **Somente vetorial (baseline)** para comparar.
3. **Pergunta sem resposta**: *O estudante João pode ser dispensado de Banco de Dados? Decida o caso dele.* O sistema deve se abster, citar a regra do regulamento e marcar confiança Baixa.
4. **Ingestão**: enviar um `.md` curto com uma disciplina nova que exige "Estrutura de Dados" (no singular) e mostrar a resolução de entidades ligando-a a `Estruturas de Dados` sem criar duplicata.
5. **Explorar caminhos**: `Projeto Integrador` → `Algoritmos`, e a tabela de PageRank.

## Perguntas prováveis da banca

- *Por que não confiar apenas no Text2Cypher?* Modelos pequenos erram a direção das relações; por isso a consulta é uma evidência a mais, e as cadeias são calculadas por consultas-modelo.
- *O que garante que o LLM não inventa?* Nada garante. O sistema reduz e torna visível o risco: as evidências são numeradas, as citações são verificadas, a resposta se abstém quando falta evidência e a confiança é exibida. A avaliação mede quanto isso funciona.
- *Por que dados sintéticos?* Permitem um gabarito exato e reprodutível e evitam questões de direitos e privacidade; a ingestão aceita documentos reais.
- *Onde está o KAG?* No uso de restrições semânticas (allowlist e assinatura de tipos), no planejamento das relações a partir da pergunta e nas cadeias lógicas entregues prontas ao LLM. O projeto não implementa o framework KAG completo com raciocínio simbólico formal.
