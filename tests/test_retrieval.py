import confidence
from retrieval import rrf, intent_relations, format_context


def test_rrf_rewards_agreement():
    assert rrf(['a', 'b'], ['b', 'c'])[0] == 'b'
    assert rrf([], ['z']) == ['z']


def test_intent_relations():
    assert intent_relations('Quais são os pré-requisitos de Projeto Integrador?') == ['EXIGE']
    assert 'EQUIVALE_A' in intent_relations('Banco de Dados equivale a qual disciplina?')
    assert 'INCLUI' in intent_relations('Quais disciplinas estão na Matriz 2026?')
    assert len(intent_relations('Fale sobre Algoritmos')) > 5  # sem pista: todas as relações


def test_format_context_numbers_every_source():
    context = {
        'chunks': [{'id': 'ppc-2026-texto-3', 'text': 'Projeto Integrador exige Banco de Dados.'}],
        'paths': [{'source_name': 'Projeto Integrador', 'relation': 'EXIGE', 'target_name': 'Banco de Dados',
                   'hops': 1, 'evidence': 'Projeto Integrador (4º período, 80 h) exige ...'}],
        'chains': [{'anchor': 'Projeto Integrador', 'relation': 'EXIGE', 'outgoing': True, 'hops': 2,
                    'nodes': ['Projeto Integrador', 'Estruturas de Dados', 'Algoritmos']}],
        'shortest': [{'nodes': ['Projeto Integrador', 'Estruturas de Dados', 'Algoritmos'], 'relations': ['EXIGE', 'EXIGE']}],
        'communities': [{'community': 3, 'anchor': 'Projeto Integrador', 'members': ['Banco de Dados']}],
    }
    text, ids, index = format_context(context, {'rows': [{'prerequisito': 'Banco de Dados'}]})
    assert ids == {'T1', 'P1', 'P2', 'P3', 'G1', 'C1'}
    assert "[P1] Cadeia EXIGE a partir de Projeto Integrador: Projeto Integrador → Estruturas de Dados → Algoritmos" in text
    assert '[P2] Projeto Integrador EXIGE (tem como pré-requisito) Banco de Dados' in text
    assert '[P3] Caminho mínimo: Projeto Integrador -EXIGE- Estruturas de Dados -EXIGE- Algoritmos' in text
    assert '[C1] prerequisito=Banco de Dados' in text


def test_citation_verification():
    check = confidence.verify_citations('Exige Banco de Dados [P1][T1] e Física [T9].', {'T1', 'P1'})
    assert check == {'cited': ['P1', 'T1', 'T9'], 'valid': ['P1', 'T1'], 'invalid': ['T9']}


def test_confidence_levels():
    good = confidence.score({'cited': ['T1'], 'valid': ['T1'], 'invalid': []}, 0.82, 2, 10, 3)
    assert good['level'] == 'Alta'
    bad = confidence.score({'cited': ['T9'], 'valid': [], 'invalid': ['T9']}, 0.55, 0, 0, 0)
    assert bad['level'] == 'Baixa' and bad['score'] == 0
    # sem LLM, a fundamentação e o Cypher saem da média
    assert set(confidence.score(None, 0.8, 1, 1, None)['signals']) == {'recuperacao', 'grafo'}
    # abstenção nunca é classificada acima de Baixa
    assert confidence.score({'cited': ['T1'], 'valid': ['T1'], 'invalid': []}, 0.9, 1, 1, 1, abstained=True)['level'] == 'Baixa'


def test_abstention_detection():
    assert confidence.is_abstention('Não há evidência suficiente para decidir a dispensa.')
    assert not confidence.is_abstention('Projeto Integrador exige Banco de Dados [P1].')
