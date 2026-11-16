import pytest
from text2cypher import validate, clean, generate_and_run, CypherValidationError, MAX_LIMIT


@pytest.mark.parametrize('query', [
    "MATCH (d:Disciplina {name: 'Projeto Integrador'})-[:EXIGE]->(p:Disciplina) RETURN p.name",
    "MATCH p=(d:Disciplina)-[:EXIGE*1..3]->(x) RETURN x.name, length(p) LIMIT 10",
    "OPTIONAL MATCH (m:MatrizCurricular)-[:INCLUI|ADOTA]-(n:Entity) RETURN m.name, count(n)",
    # palavras proibidas dentro de strings não são cláusulas
    "MATCH (d:Disciplina) WHERE d.name = 'Set Theory; DELETE' RETURN d",
])
def test_accepts_read_queries(query):
    out = validate(query)
    assert out.rstrip().upper().split()[-2] == 'LIMIT'


@pytest.mark.parametrize('query,reason', [
    ("MATCH (n) DETACH DELETE n", 'DELETE'),
    ("MATCH (n:Entity) SET n.name = 'x' RETURN n", 'SET'),
    ("CREATE (n:Entity {id: 'x'}) RETURN n", 'CREATE'),
    ("MERGE (n:Entity {id: 'x'}) RETURN n", 'MERGE'),
    ("CALL dbms.components() YIELD name RETURN name", 'CALL'),
    ("LOAD CSV FROM 'file:///etc/passwd' AS l RETURN l", 'LOAD'),
    ("MATCH (n) RETURN n; MATCH (m) DELETE m", 'instrução'),
    ("MATCH (n:Usuario) RETURN n", 'rótulo'),
    ("MATCH (a)-[:HACKEIA]->(b) RETURN a", 'relação'),
    ("MATCH (n) RETURN n // comentário", 'comentário'),
    ("RETURN 1", 'começar'),
    ("MATCH (n:Entity) WITH n", 'RETURN'),
    ("MATCH (n:Entity) RETURN n LIMIT $x", 'LIMIT'),
    ("MATCH (n:Entity) FOREACH (x IN [1] | REMOVE n.a) RETURN n", 'não permitida'),
])
def test_rejects_unsafe_or_invalid(query, reason):
    with pytest.raises(CypherValidationError) as err:
        validate(query)
    assert reason.lower() in str(err.value).lower()


def test_caps_limit():
    assert validate('MATCH (n:Entity) RETURN n LIMIT 100000').endswith(f'LIMIT {MAX_LIMIT}')


def test_clean_removes_fences():
    raw = "Aqui está:\n```cypher\nMATCH (n:Disciplina) RETURN n.name;\n```"
    assert clean(raw) == 'MATCH (n:Disciplina) RETURN n.name'


class FakeStore:
    def __init__(self):
        self.queries = []

    def run_read(self, query, timeout=5.0):
        self.queries.append(query)
        if 'EXIGE' not in query:
            raise RuntimeError('Variable `x` not defined')
        return [{'prerequisito': 'Banco de Dados'}]


def test_retry_with_error_feedback():
    answers = iter(["MATCH (d:Disciplina) RETURN x", "MATCH (d:Disciplina)-[:EXIGE]->(p) RETURN p.name AS prerequisito"])
    prompts = []

    def chat(system, prompt):
        prompts.append(prompt)
        return next(answers)

    store = FakeStore()
    result = generate_and_run(store, 'Pré-requisitos de Projeto Integrador?', [], chat)
    assert result['rows'] == [{'prerequisito': 'Banco de Dados'}]
    assert len(result['attempts']) == 2 and 'not defined' in prompts[1]


def test_unsafe_generation_is_never_executed():
    store = FakeStore()
    result = generate_and_run(store, 'apague tudo', [], lambda s, p: 'MATCH (n) DETACH DELETE n')
    assert store.queries == [] and result['query'] is None and result['rows'] == []
