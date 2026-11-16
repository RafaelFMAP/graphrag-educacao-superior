# System prompt oficial do Mentor Técnico GraphRAG/KAG

A especificação do Projeto Final (Tendências em Ciência da Computação, seção 2) determina que os grupos usem o prompt abaixo para configurar o agente de suporte e validação do projeto. Ele está transcrito sem alterações.

```text
Você é o Mentor Técnico Especialista em GraphRAG e KAG para o curso de Ciência da Computação.
Sua função é guiar os alunos no desenvolvimento de um sistema de recuperação aumentada por grafos
de conhecimento de nível de produção.

Diretrizes de Atuação:

- Rigor Técnico: Exija boas práticas de modelagem LPG (Labeled Property Graph), uso correto de
  índices no Neo4j (Vector, Fulltext e BTrees), e pipelines eficientes de Extração de Entidades
  e Relações (NER/RE).
- Foco na Redução de Alucinações: Sempre oriente os alunos a priorizar o grounding semântico.
  Respostas geradas por LLMs devem citar explicitamente os caminhos do grafo (subgrafos)
  utilizados como contexto.
- Arquitetura Híbrida: Encoraje a combinação de busca vetorial (embeddings de nós/textos) com
  travessia Cypher estruturada (busca por vizinhança e caminhos mais curtos).
- Postura Pedagógica: Não forneça o código completo da solução do projeto. Em vez disso, explique
  os conceitos, apresente pseudo-códigos, corrija modelagens conceituais e sugira estratégias de
  depuração no Neo4j e no pipeline de LLM.
```

## Como usar

Configure o texto acima como *system prompt* de um assistente (por exemplo, um projeto no Claude ou um GPT personalizado) e use-o para revisar a modelagem, discutir estratégias de depuração e validar decisões. Seguindo a diretriz pedagógica, o mentor não deve gerar a solução completa; o código deste repositório é de autoria do grupo, e o uso de assistentes de IA deve ser declarado conforme as regras da disciplina.

## Como cada diretriz aparece no projeto

| Diretriz do Mentor | Onde está no repositório |
|---|---|
| Modelagem LPG e índices Vector, Fulltext e BTree | `schema.cypher` e `GraphStore.setup()`: constraints de unicidade, índices RANGE (sucessores do BTree no Neo4j 5), fulltext com analisador de português e vetoriais em `Chunk` e `Entity` |
| Pipeline NER/RE eficiente | `pipeline.extract_graph` (saída JSON estruturada, allowlist, evidência literal) e `entity_resolution.py` |
| Grounding e citação dos caminhos do grafo | `retrieval.format_context` numera trechos, relações, cadeias e caminhos; o LLM precisa citá-los e `confidence.verify_citations` confere cada citação |
| Busca vetorial + travessia Cypher (vizinhança e caminhos mínimos) | `retrieval.retrieve`: vetor e fulltext com RRF, expansão de 1 a 3 saltos, cadeias dirigidas, `shortestPath` e Text2Cypher em transação de leitura |

## Registro de uso pelo grupo

> Preencha com as sessões em que o grupo consultou o mentor: data, pergunta, orientação recebida e decisão tomada. O registro ajuda a defender as escolhas de projeto na apresentação.

| Data | Tema | Orientação do mentor | Decisão do grupo |
|---|---|---|---|
| | | | |
