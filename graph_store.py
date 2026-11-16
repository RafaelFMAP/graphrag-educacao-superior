"""Neo4j LPG, constraints, indexes, and evidence-constrained queries."""
import re
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, DOMAIN

SCHEMA = [
    # Unicidade (constraints também criam índices RANGE de apoio)
    "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (n:Chunk) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (n:Document) REQUIRE n.id IS UNIQUE",
    # Índices RANGE (sucessores do BTree no Neo4j 5) para filtros e ordenações por propriedade
    "CREATE INDEX entity_name IF NOT EXISTS FOR (n:Entity) ON (n.name)",
    "CREATE INDEX entity_kind IF NOT EXISTS FOR (n:Entity) ON (n.kind)",
    "CREATE INDEX document_version IF NOT EXISTS FOR (n:Document) ON (n.version)",
    "CREATE INDEX chunk_locator IF NOT EXISTS FOR (n:Chunk) ON (n.locator)",
    "CREATE INDEX entity_community IF NOT EXISTS FOR (n:Entity) ON (n.community)",
    "CREATE INDEX entity_pagerank IF NOT EXISTS FOR (n:Entity) ON (n.pagerank)",
    # Fulltext (Lucene) com analisador "brazilian": radicaliza o português ("dispensado" casa com "dispensa")
    "CREATE FULLTEXT INDEX entity_text IF NOT EXISTS FOR (n:Entity) ON EACH [n.name, n.id, n.aliases_text] OPTIONS {indexConfig: {`fulltext.analyzer`: 'brazilian'}}",
    "CREATE FULLTEXT INDEX chunk_text IF NOT EXISTS FOR (n:Chunk) ON EACH [n.text] OPTIONS {indexConfig: {`fulltext.analyzer`: 'brazilian'}}",
    # Vetoriais: nomic-embed-text usa 768 dimensões; funciona só com esse formato
    "CREATE VECTOR INDEX chunk_vector IF NOT EXISTS FOR (n:Chunk) ON (n.embedding) OPTIONS {indexConfig: {`vector.dimensions`: 768, `vector.similarity_function`: 'cosine'}}",
    "CREATE VECTOR INDEX entity_vector IF NOT EXISTS FOR (n:Entity) ON (n.embedding) OPTIONS {indexConfig: {`vector.dimensions`: 768, `vector.similarity_function`: 'cosine'}}",
]


def compact(value):
    """Reduz nós devolvidos pelo Text2Cypher ao nome, sem embeddings, para caber no prompt."""
    if isinstance(value, dict):
        if 'name' in value:
            return value['name']
        return {k: compact(v) for k, v in value.items() if k not in ('embedding', 'aliases_text')}
    if isinstance(value, list):
        return [compact(v) for v in value[:50]]
    return value


def lucene_terms(text, limit=8):
    """Sanitized OR query; prevents Lucene syntax injection and bad wildcard queries."""
    terms = re.findall(r"[\wÀ-ÿ]{2,}", text)
    terms = [t for t in terms if len(t) >= 3 or t.isupper()]
    return ' OR '.join(terms[:limit])


class GraphStore:
    def __init__(self, driver=None):
        if driver is None:
            from neo4j import GraphDatabase
            # Avisos como "tipo de relação inexistente" (ex.: PERTENCE_A sem uso) não são erros.
            driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD), notifications_min_severity='OFF')
        self.driver = driver

    def close(self): self.driver.close()

    def run(self, query, **params):
        with self.driver.session() as session:
            return [r.data() for r in session.run(query, **params)]

    def run_read(self, query, timeout=5.0, **params):
        """Executa em transação de LEITURA com timeout: o Neo4j recusa qualquer escrita."""
        from neo4j import READ_ACCESS, unit_of_work

        @unit_of_work(timeout=timeout)
        def work(tx):
            return [compact(r.data()) for r in tx.run(query, **params)]
        with self.driver.session(default_access_mode=READ_ACCESS) as session:
            return session.execute_read(work)

    # ---------- schema ----------
    def setup(self):
        # Migração: versões anteriores criaram os fulltext sem aliases e sem analisador de português.
        for row in self.run("""SHOW INDEXES YIELD name, properties, options
                WHERE name IN ['entity_text', 'chunk_text'] RETURN name, properties, options"""):
            analyzer = (row['options'] or {}).get('indexConfig', {}).get('fulltext.analyzer')
            if analyzer != 'brazilian' or (row['name'] == 'entity_text' and 'aliases_text' not in row['properties']):
                self.run(f"DROP INDEX {row['name']}")
        for statement in SCHEMA:
            self.run(statement)

    # ---------- escrita ----------
    def put_entity(self, entity):
        # Dynamic labels are checked against the project's explicit allowlist.
        label = entity["label"]
        if label not in DOMAIN["labels"]:
            raise ValueError("Rótulo não permitido: " + label)
        aliases = [a for a in entity.get("aliases", []) if a and a != entity["name"]]
        # O rótulo só é atribuído na criação: um nó existente nunca é reetiquetado.
        self.run(f"""MERGE (n:Entity {{id:$id}}) ON CREATE SET n:`{label}`, n.kind=$kind
            SET n.name=$name, n.aliases=$aliases, n.aliases_text=reduce(s='', a IN $aliases | s + ' ' + a),
            n.embedding=coalesce($embedding, n.embedding)""",
                 id=entity['id'], name=entity['name'], kind=label, aliases=aliases, embedding=entity.get('embedding'))

    def add_alias(self, entity_id, alias):
        self.run("""MATCH (n:Entity {id:$id}) WHERE $alias <> n.name AND NOT $alias IN coalesce(n.aliases, [])
            SET n.aliases = coalesce(n.aliases, []) + $alias
            SET n.aliases_text = reduce(s='', a IN n.aliases | s + ' ' + a)""", id=entity_id, alias=alias)

    def put_edge(self, edge):
        """Grava a relação só se respeitar a allowlist e a assinatura de tipos do domínio.

        Retorna False quando a assinatura (rótulo de origem -> rótulo de destino) não é
        permitida, por exemplo Curso -ADOTA-> Documento; a relação não é gravada.
        """
        relation = edge["type"]
        if relation not in DOMAIN["relations"]:
            raise ValueError("Relação não permitida: " + relation)
        sources, targets = DOMAIN["relation_signatures"][relation]
        rows = self.run(f"""MATCH (a:Entity {{id:$source}}), (b:Entity {{id:$target}})
            WHERE a.kind IN $sources AND b.kind IN $targets
            MERGE (a)-[r:`{relation}`]->(b)
            SET r.evidence_id=$evidence_id, r.evidence=$evidence, r.source_type=$source_type
            RETURN count(r) AS n""",
                        source=edge['source'], target=edge['target'], sources=sources, targets=targets,
                        evidence_id=edge.get('evidence_id', ''), evidence=edge.get('evidence', ''),
                        source_type=edge.get('source_type', 'extracted'))
        return bool(rows and rows[0]['n'])

    def put_document(self, document):
        self.run("MERGE (d:Document {id:$id}) SET d.title=$title,d.version=$version,d.origin=$origin", **document)

    def link_document_entity(self, entity_id, doc_id):
        """Liga a entidade de domínio :Documento ao nó :Document que guarda os trechos."""
        self.run("MATCH (e:Entity {id:$e}), (d:Document {id:$d}) MERGE (e)-[:REPRESENTA]->(d)", e=entity_id, d=doc_id)

    def put_chunk(self, chunk):
        self.run("MATCH (d:Document {id:$doc_id}) MERGE (c:Chunk {id:$id}) SET c.text=$text,c.locator=$locator,c.embedding=$embedding MERGE (c)-[:FROM_DOCUMENT]->(d)", **chunk)

    def link_mention(self, chunk_id, entity_id):
        self.run("MATCH (c:Chunk {id:$c}),(e:Entity {id:$e}) MERGE (c)-[:MENTIONS]->(e)", c=chunk_id, e=entity_id)

    # ---------- leitura para resolução de entidades e seed ----------
    def entity_candidates(self, label=None):
        return self.run("""MATCH (n:Entity) WHERE $label IS NULL OR n.kind=$label
            RETURN n.id AS id, n.name AS name, n.kind AS label, coalesce(n.aliases, []) AS aliases""", label=label)

    def vector_entities(self, embedding, limit=5):
        if not embedding: return []
        return self.run("""CALL db.index.vector.queryNodes('entity_vector',$k,$v) YIELD node,score
            RETURN node.id AS id, node.name AS name, node.kind AS label, score""", k=limit, v=embedding)

    def chunk_with_text(self, doc_id, excerpt):
        rows = self.run("""MATCH (c:Chunk)-[:FROM_DOCUMENT]->(:Document {id:$doc}) WHERE c.text CONTAINS $excerpt
            RETURN c.id AS id ORDER BY c.id LIMIT 1""", doc=doc_id, excerpt=excerpt)
        return rows[0]['id'] if rows else None

    # ---------- recuperação ----------
    def fulltext_chunks(self, q, limit=6):
        lucene = lucene_terms(q)
        if not lucene: return []
        return self.run("CALL db.index.fulltext.queryNodes('chunk_text',$q) YIELD node,score RETURN node.id AS id,node.text AS text,node.locator AS locator,score LIMIT $k", q=lucene, k=limit)

    def vector_chunks(self, embedding, limit=6):
        if not embedding: return []
        return self.run("CALL db.index.vector.queryNodes('chunk_vector',$k,$v) YIELD node,score RETURN node.id AS id,node.text AS text,node.locator AS locator,score", k=limit, v=embedding)

    def nearby(self, term, limit=30):
        lucene = lucene_terms(term)
        if not lucene: return []
        # Fulltext anchor + 1..3 hops, fixed query, no user-authored Cypher.
        return self.run("""CALL db.index.fulltext.queryNodes('entity_text',$term) YIELD node,score
        WITH node ORDER BY score DESC LIMIT 5
        MATCH p=(node)-[*1..3]-(other:Entity)
        WHERE all(x IN nodes(p) WHERE x:Entity)
        UNWIND relationships(p) AS r
        WITH DISTINCT startNode(r) AS a,endNode(r) AS b,r
        RETURN a.id AS source,a.name AS source_name,type(r) AS relation,
               b.id AS target,b.name AS target_name,r.evidence_id AS evidence_id,r.evidence AS evidence
        LIMIT $limit""", term=lucene, limit=limit)

    def fulltext_entities(self, q, limit=5):
        lucene = lucene_terms(q)
        if not lucene: return []
        return self.run("""CALL db.index.fulltext.queryNodes('entity_text',$q) YIELD node,score
            RETURN node.id AS id, node.name AS name, node.kind AS label, score LIMIT $k""", q=lucene, k=limit)

    def chunks_by_id(self, ids):
        if not ids: return []
        return self.run("""MATCH (c:Chunk) WHERE c.id IN $ids
            RETURN c.id AS id, c.text AS text, c.locator AS locator, 0.0 AS score""", ids=list(ids))

    @staticmethod
    def expand_query(relations):
        """Consulta-modelo da expansão multi-hop; os tipos vêm da allowlist, nunca do usuário."""
        types = [r for r in relations if r in DOMAIN["relations"]] or DOMAIN["relations"]
        return f"""MATCH p=(anchor:Entity)-[:{'|'.join(types)}*1..3]-(other:Entity)
WHERE anchor.id IN $anchors
  AND all(n IN nodes(p)[1..-1] WHERE COUNT {{ (n)--(:Entity) }} <= $max_degree)
UNWIND range(0, length(p) - 1) AS i
WITH relationships(p)[i] AS r, i + 1 AS hops
WITH r, min(hops) AS hops
WITH startNode(r) AS a, r, endNode(r) AS b, hops
RETURN a.id AS source, a.name AS source_name, a.kind AS source_label, type(r) AS relation,
       b.id AS target, b.name AS target_name, b.kind AS target_label,
       r.evidence_id AS evidence_id, r.evidence AS evidence, hops,
       round(coalesce(a.pagerank, 0) + coalesce(b.pagerank, 0), 3) AS pagerank
ORDER BY hops, pagerank DESC LIMIT $limit"""

    def expand(self, anchor_ids, relations, limit=40, max_degree=15):
        """1 a 3 saltos a partir das âncoras, sem atravessar hubs (grau > max_degree),
        ordenados por distância e PageRank."""
        return self.run(self.expand_query(relations), anchors=list(anchor_ids), limit=limit, max_degree=max_degree)

    def chains(self, anchor_ids, relation, outgoing=True, max_hops=4, limit=8):
        """Cadeias dirigidas maximais de uma relação a partir das âncoras (raciocínio multi-hop explícito).

        outgoing=True: âncora -> ... (ex.: pré-requisitos diretos e indiretos via EXIGE);
        outgoing=False: ... -> âncora (ex.: disciplinas que dependem da âncora).
        """
        if relation not in DOMAIN["relations"]:
            raise ValueError("Relação não permitida: " + relation)
        if outgoing:
            query = f"""MATCH p=(a:Entity)-[:`{relation}`*1..{int(max_hops)}]->(x:Entity)
                WHERE a.id IN $ids AND (length(p) = {int(max_hops)} OR NOT (x)-[:`{relation}`]->(:Entity))
                RETURN a.name AS anchor, [n IN nodes(p) | n.name] AS nodes, length(p) AS hops
                ORDER BY hops DESC LIMIT $k"""
        else:
            query = f"""MATCH p=(x:Entity)-[:`{relation}`*1..{int(max_hops)}]->(a:Entity)
                WHERE a.id IN $ids AND (length(p) = {int(max_hops)} OR NOT (:Entity)-[:`{relation}`]->(x))
                RETURN a.name AS anchor, [n IN nodes(p) | n.name] AS nodes, length(p) AS hops
                ORDER BY hops DESC LIMIT $k"""
        return [{**r, 'relation': relation, 'outgoing': outgoing} for r in self.run(query, ids=list(anchor_ids), k=limit)]

    def shortest_path_ids(self, source_id, target_id, max_degree=15):
        return self.run("""MATCH (a:Entity {id:$a}),(b:Entity {id:$b})
        MATCH p=shortestPath((a)-[*..6]-(b))
        WHERE all(n IN nodes(p) WHERE n:Entity)
          AND all(n IN nodes(p) WHERE n = a OR n = b OR COUNT { (n)--(:Entity) } <= $max_degree)
        RETURN [n IN nodes(p)|n.name] AS nodes, [n IN nodes(p)|n.id] AS ids,
               [r IN relationships(p)|type(r)] AS relations""", a=source_id, b=target_id, max_degree=max_degree)

    def communities_of(self, anchor_ids, members=6):
        return self.run("""MATCH (a:Entity) WHERE a.id IN $ids AND coalesce(a.community, -1) >= 0
        MATCH (m:Entity {community: a.community}) WHERE m <> a
        WITH a, m ORDER BY m.pagerank DESC
        WITH a, collect(m.name)[..$k] AS members
        RETURN a.name AS anchor, a.community AS community, members""", ids=list(anchor_ids), k=members)

    def entity_details(self, ids):
        if not ids: return []
        return self.run("""MATCH (n:Entity) WHERE n.id IN $ids
            RETURN n.id AS id, n.name AS name, n.kind AS label,
                   round(coalesce(n.pagerank, 0), 3) AS pagerank, n.community AS community""", ids=list(ids))

    def shortest_path(self, source_id, target_id):
        return self.run("""MATCH (a:Entity {id:$a}),(b:Entity {id:$b})
        MATCH p=shortestPath((a)-[*..8]-(b))
        WHERE all(n IN nodes(p) WHERE n:Entity)
        RETURN [n IN nodes(p)|n.name] AS nodes,
               [r IN relationships(p)|type(r)] AS relations""", a=source_id, b=target_id)

    def evidence_for_relation(self, source, target, relation):
        return self.run("""MATCH (a:Entity {id:$a})-[r]->(b:Entity {id:$b})
        WHERE type(r)=$rel RETURN r.evidence_id AS evidence_id, r.evidence AS evidence""", a=source, b=target, rel=relation)
