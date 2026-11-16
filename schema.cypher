// Schema LPG do projeto (Neo4j 5). Criado automaticamente por GraphStore.setup();
// este arquivo documenta o modelo e permite aplicá-lo à mão no Neo4j Browser.
//
// Nós
//   (:Entity:<Rótulo>)  id, name, kind, aliases[], aliases_text, embedding[768],
//                       pagerank, community (gravados pelos algoritmos de grafo)
//   (:Document)         id, title, version, origin
//   (:Chunk)            id, text, locator, embedding[768]
// Relações estruturais
//   (:Chunk)-[:FROM_DOCUMENT]->(:Document)
//   (:Chunk)-[:MENTIONS]->(:Entity)
//   (:Entity:Documento)-[:REPRESENTA]->(:Document)
// Relações de domínio (allowlist em domain.json), sempre com procedência:
//   evidence (frase literal), evidence_id (id do Chunk), source_type
//   (synthetic_seed | llm_verified_excerpt)

// Unicidade
CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (n:Chunk) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (n:Document) REQUIRE n.id IS UNIQUE;

// Índices RANGE (substitutos do BTree a partir do Neo4j 5)
CREATE INDEX entity_name IF NOT EXISTS FOR (n:Entity) ON (n.name);
CREATE INDEX entity_kind IF NOT EXISTS FOR (n:Entity) ON (n.kind);
CREATE INDEX document_version IF NOT EXISTS FOR (n:Document) ON (n.version);
CREATE INDEX chunk_locator IF NOT EXISTS FOR (n:Chunk) ON (n.locator);

// Fulltext (Lucene)
CREATE FULLTEXT INDEX entity_text IF NOT EXISTS FOR (n:Entity) ON EACH [n.name, n.id, n.aliases_text];
CREATE FULLTEXT INDEX chunk_text IF NOT EXISTS FOR (n:Chunk) ON EACH [n.text];

// Vetoriais (nomic-embed-text, 768 dimensões, cosseno)
CREATE VECTOR INDEX chunk_vector IF NOT EXISTS FOR (n:Chunk) ON (n.embedding)
  OPTIONS {indexConfig: {`vector.dimensions`: 768, `vector.similarity_function`: 'cosine'}};
CREATE VECTOR INDEX entity_vector IF NOT EXISTS FOR (n:Entity) ON (n.embedding)
  OPTIONS {indexConfig: {`vector.dimensions`: 768, `vector.similarity_function`: 'cosine'}};
