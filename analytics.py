"""Algoritmos de grafo (Neo4j Graph Data Science) que enriquecem o contexto do LLM.

- PageRank (grafo dirigido): importância estrutural de cada entidade. Disciplinas
  exigidas por muitas outras, como Algoritmos, recebem pontuação alta. A
  recuperação usa o valor para ordenar os caminhos enviados ao LLM.
- Leiden (grafo não dirigido; Louvain se o Leiden não estiver disponível):
  comunidades de entidades relacionadas. O contexto informa a comunidade de
  cada entidade-âncora e os membros mais centrais dela.

Os resultados são gravados nas propriedades `pagerank` e `community` dos nós
`Entity`. Execute depois de cada carga ou ingestão: `python analytics.py`.
"""
from graph_store import GraphStore

DIRECTED = 'entidades_dirigido'
UNDIRECTED = 'entidades_nao_dirigido'


def _project(store, name, undirected):
    store.run("CALL gds.graph.drop($name, false) YIELD graphName RETURN graphName", name=name)
    # EQUIVALE_A é simétrica: no grafo dirigido ela é projetada sem direção para não
    # acumular PageRank na disciplina antiga da equivalência.
    config = "{undirectedRelationshipTypes: ['*']}" if undirected else "{undirectedRelationshipTypes: ['EQUIVALE_A']}"
    rows = store.run(f"""MATCH (a:Entity)
        OPTIONAL MATCH (a)-[r]->(b:Entity)
        WITH gds.graph.project($name, a, b, {{relationshipType: type(r)}}, {config}) AS g
        RETURN g.nodeCount AS nodes, g.relationshipCount AS relationships""", name=name)
    return rows[0]


def run_analytics(store):
    version = store.run("RETURN gds.version() AS v")[0]['v']
    graph = _project(store, DIRECTED, undirected=False)
    pagerank = store.run(f"""CALL gds.pageRank.write('{DIRECTED}', {{writeProperty: 'pagerank', maxIterations: 40, dampingFactor: 0.85}})
        YIELD nodePropertiesWritten, ranIterations RETURN nodePropertiesWritten AS nodes, ranIterations AS iterations""")[0]
    _project(store, UNDIRECTED, undirected=True)
    try:
        community = store.run(f"""CALL gds.leiden.write('{UNDIRECTED}', {{writeProperty: 'community', randomSeed: 42, concurrency: 1}})
            YIELD communityCount, modularity RETURN communityCount AS communities, modularity, 'Leiden' AS algorithm""")[0]
    except Exception:
        community = store.run(f"""CALL gds.louvain.write('{UNDIRECTED}', {{writeProperty: 'community', concurrency: 1}})
            YIELD communityCount, modularity RETURN communityCount AS communities, modularity, 'Louvain' AS algorithm""")[0]
    for name in (DIRECTED, UNDIRECTED):
        store.run("CALL gds.graph.drop($name, false) YIELD graphName RETURN graphName", name=name)
    # Entidades isoladas não entram na projeção: recebem valores neutros.
    store.run("MATCH (n:Entity) WHERE n.pagerank IS NULL SET n.pagerank = 0.0")
    store.run("MATCH (n:Entity) WHERE n.community IS NULL SET n.community = -1")
    return {'gds': version, 'nodes': graph['nodes'], 'relationships': graph['relationships'],
            'pagerank_iterations': pagerank['iterations'], 'algorithm': community['algorithm'],
            'communities': community['communities'], 'modularity': round(community['modularity'], 3)}


def top_entities(store, limit=10):
    return store.run("""MATCH (n:Entity) RETURN n.name AS name, n.kind AS label,
        round(n.pagerank, 3) AS pagerank, n.community AS community ORDER BY n.pagerank DESC LIMIT $k""", k=limit)


if __name__ == '__main__':
    s = GraphStore()
    try:
        print(run_analytics(s))
        for row in top_entities(s):
            print(row)
    finally:
        s.close()
