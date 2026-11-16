"""Neo4j LPG, constraints, indexes, and evidence-constrained queries."""
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, DOMAIN

class GraphStore:
    def __init__(self, driver=None):
        if driver is None:
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        self.driver = driver

    def close(self): self.driver.close()

    def run(self, query, **params):
        with self.driver.session() as session:
            return [r.data() for r in session.run(query, **params)]

    def setup(self):
        self.run("CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE")
        self.run("CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (n:Chunk) REQUIRE n.id IS UNIQUE")
        self.run("CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (n:Document) REQUIRE n.id IS UNIQUE")
        self.run("CREATE FULLTEXT INDEX entity_text IF NOT EXISTS FOR (n:Entity) ON EACH [n.name, n.id]")
        self.run("CREATE FULLTEXT INDEX chunk_text IF NOT EXISTS FOR (n:Chunk) ON EACH [n.text]")
        # nomic-embed-text uses 768 dimensions; works only with that model.
        self.run("CREATE VECTOR INDEX chunk_vector IF NOT EXISTS FOR (n:Chunk) ON (n.embedding) OPTIONS {indexConfig: {`vector.dimensions`: 768, `vector.similarity_function`: 'cosine'}}")

    def put_entity(self, entity):
        # Dynamic labels are checked against the project's explicit allowlist.
        label = entity["label"]
        if label not in DOMAIN["labels"]:
            raise ValueError("Rótulo não permitido: " + label)
        self.run(f"MERGE (n:Entity:`{label}` {{id:$id}}) SET n.name=$name, n.kind=$kind", id=entity['id'],name=entity['name'],kind=label)

    def put_edge(self, edge):
        relation = edge["type"]
        if relation not in DOMAIN["relations"]:
            raise ValueError("Relação não permitida: " + relation)
        self.run(f"MATCH (a:Entity {{id:$source}}), (b:Entity {{id:$target}}) MERGE (a)-[r:`{relation}`]->(b) SET r.evidence_id=$evidence, r.source_type=$source_type",source=edge['source'],target=edge['target'],evidence=edge.get('evidence_id',''),source_type=edge.get('source_type','extracted'))

    def put_document(self, document):
        self.run("MERGE (d:Document {id:$id}) SET d.title=$title,d.version=$version,d.origin=$origin",**document)

    def put_chunk(self, chunk):
        self.run("MATCH (d:Document {id:$doc_id}) MERGE (c:Chunk {id:$id}) SET c.text=$text,c.locator=$locator,c.embedding=$embedding MERGE (c)-[:FROM_DOCUMENT]->(d)",**chunk)

    def link_mention(self, chunk_id, entity_id):
        self.run("MATCH (c:Chunk {id:$c}),(e:Entity {id:$e}) MERGE (c)-[:MENTIONS]->(e)",c=chunk_id,e=entity_id)

    def fulltext_chunks(self, q, limit=6):
        # Sanitization prevents Lucene syntax injection and bad wildcard queries.
        import re
        terms = re.findall(r"[\wÀ-ÿ]{3,}",q)
        if not terms: return []
        lucene = ' OR '.join(terms[:8])
        return self.run("CALL db.index.fulltext.queryNodes('chunk_text',$q) YIELD node,score RETURN node.id AS id,node.text AS text,node.locator AS locator,score LIMIT $k",q=lucene,k=limit)

    def vector_chunks(self, embedding, limit=6):
        if not embedding: return []
        return self.run("CALL db.index.vector.queryNodes('chunk_vector',$k,$v) YIELD node,score RETURN node.id AS id,node.text AS text,node.locator AS locator,score", k=limit,v=embedding)

    def nearby(self, term, limit=30):
        import re
        terms = re.findall(r"[\wÀ-ÿ]{3,}",term)
        if not terms: return []
        # Fulltext anchor + 1..3 hops, fixed query, no user-authored Cypher.
        return self.run("""CALL db.index.fulltext.queryNodes('entity_text',$term) YIELD node,score
        WITH node ORDER BY score DESC LIMIT 5
        MATCH p=(node)-[*1..3]-(other:Entity)
        WHERE all(x IN nodes(p) WHERE x:Entity)
        UNWIND relationships(p) AS r
        WITH DISTINCT startNode(r) AS a,endNode(r) AS b,r
        RETURN a.id AS source,a.name AS source_name,type(r) AS relation,
               b.id AS target,b.name AS target_name,r.evidence_id AS evidence_id
        LIMIT $limit""",term=' OR '.join(terms[:8]),limit=limit)

    def shortest_path(self, source_id, target_id):
        return self.run("""MATCH (a:Entity {id:$a}),(b:Entity {id:$b})
        MATCH p=shortestPath((a)-[*..8]-(b))
        WHERE all(n IN nodes(p) WHERE n:Entity)
        RETURN [n IN nodes(p)|n.name] AS nodes,
               [r IN relationships(p)|type(r)] AS relations""",a=source_id,b=target_id)

    def evidence_for_relation(self, source, target, relation):
        return self.run("""MATCH (a:Entity {id:$a})-[r]->(b:Entity {id:$b})
        WHERE type(r)=$rel RETURN r.evidence_id AS evidence_id""",a=source,b=target,rel=relation)
