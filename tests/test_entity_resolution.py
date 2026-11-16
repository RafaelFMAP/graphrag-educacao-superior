import json
from pathlib import Path
import pytest
from entity_resolution import EntityResolver, compatible, acronym_key

SEED = json.loads((Path(__file__).parent.parent / 'data' / 'seed.json').read_text(encoding='utf8'))


class FakeStore:
    """Fornece as entidades do grafo-gabarito, sem Neo4j."""
    def __init__(self, entities, vector_hits=()):
        self.entities = entities
        self.vector_hits = list(vector_hits)

    def entity_candidates(self, label=None):
        return [e for e in self.entities if label is None or e['label'] == label]

    def vector_entities(self, embedding, limit=5):
        return self.vector_hits[:limit]


@pytest.fixture
def resolver():
    return EntityResolver(FakeStore(SEED['entities']))


@pytest.mark.parametrize('name,expected,method', [
    ('Estruturas de Dados', 'estruturas-de-dados', 'id'),
    ('ESTRUTURAS DE DADOS', 'estruturas-de-dados', 'id'),
    ('Estrutura de Dados', 'estruturas-de-dados', 'fuzzy'),
    ('Algoritmo', 'algoritmos', 'fuzzy'),
    ('POO', 'programacao-orientada-a-objetos', 'alias'),
    ('Machine Learning', 'aprendizado-de-maquina', 'alias'),
    ('TCC II', 'trabalho-de-conclusao-de-curso-ii', 'alias'),
    ('IHC', 'interacao-humano-computador', 'alias'),
    ('PAA', 'projeto-e-analise-de-algoritmos', 'alias'),
    ('EDA', 'estruturas-de-dados-avancadas', 'sigla'),
])
def test_resolves_known_disciplines(resolver, name, expected, method):
    ident, how, _ = resolver.resolve(name, 'Disciplina')
    assert (ident, how) == (expected, method)


@pytest.mark.parametrize('name', ['Cálculo III', 'Banco de Dados II', 'Estruturas de Dados III', 'Física Quântica'])
def test_does_not_merge_different_entities(resolver, name):
    _, how, _ = resolver.resolve(name, 'Disciplina')
    assert how == 'novo'


def test_label_restricts_resolution(resolver):
    # Entre as competências só há "Inteligência Artificial Aplicada", que a proteção de
    # extensão impede de fundir; o nome existe como Disciplina, e esse rótulo prevalece.
    assert resolver.resolve('Inteligência Artificial', 'Competencia')[:2] == ('inteligencia-artificial', 'rótulo divergente')
    assert resolver.resolve('Inteligência Artificial', 'Disciplina')[1] == 'id'
    assert resolver.resolve('IA Aplicada', 'Competencia')[1] == 'novo'


def test_guards():
    assert not compatible('Cálculo I', 'Cálculo II')
    assert not compatible('Banco de Dados', 'Banco de Dados Avançado')
    assert not compatible('Estruturas de Dados', 'Estruturas de Dados I')
    assert compatible('Estrutura de Dados', 'Estruturas de Dados')
    assert acronym_key('Trabalho de Conclusão de Curso I') == ('tcc', frozenset({'i'}))


def test_vector_match_respects_threshold_and_guards():
    store = FakeStore([], vector_hits=[
        {'id': 'banco-de-dados', 'name': 'Banco de Dados', 'label': 'Disciplina', 'score': 0.99},
        {'id': 'bases-de-dados', 'name': 'Bases de Dados', 'label': 'Disciplina', 'score': 0.98},
    ])
    r = EntityResolver(store, embed_fn=lambda text: [0.0] * 768)
    # bloqueado pela proteção de extensão; o segundo candidato passa
    assert r.resolve('Banco de Dados Avançado', 'Disciplina')[:2] == ('bases-de-dados', 'vetor')
    r = EntityResolver(store, embed_fn=lambda text: [0.0] * 768, vector_threshold=0.995)
    assert r.resolve('Sistemas de Dados', 'Disciplina')[1] == 'novo'


def test_new_entity_is_remembered(resolver):
    ident, how, _ = resolver.resolve('Física Quântica', 'Disciplina')
    resolver.remember(ident, 'Física Quântica', 'Disciplina')
    assert resolver.resolve('Fisica Quantica', 'Disciplina')[:2] == ('fisica-quantica', 'id')


def test_digits_equal_roman_numerals():
    assert compatible('Cálculo 2', 'Cálculo II')
    assert not compatible('Cálculo 2', 'Cálculo I')


def test_existing_label_wins_on_conflict(resolver):
    # o modelo rotulou uma disciplina conhecida como Instituicao: reaproveita o nó, sem reetiquetar
    assert resolver.resolve('Algoritmos', 'Instituicao')[:2] == ('algoritmos', 'rótulo divergente')
    assert resolver.resolve('POO', 'Curso')[:2] == ('programacao-orientada-a-objetos', 'rótulo divergente')
