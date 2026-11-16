import json
from pathlib import Path
from evaluate import norm, coverage, summarize, markdown
from evaluate_extraction import prf, GoldCatalog

ROOT = Path(__file__).parent.parent


def test_questions_have_ground_truth():
    items = json.loads((ROOT / 'data' / 'questions.json').read_text(encoding='utf8'))
    seed = json.loads((ROOT / 'data' / 'seed.json').read_text(encoding='utf8'))
    names = {e['name'] for e in seed['entities']}
    assert len(items) >= 30 and any(not x['answerable'] for x in items)
    for x in items:
        if x['answerable']:
            assert x['expected_entities'] or x['expected_facts'], x['id']
            assert set(x['expected_entities']) <= names
            assert x['hops'] >= 1
        assert not x['needs_manual_review']


def test_coverage_and_normalization():
    assert norm('Pré-Requisito ÉTICO') == 'pre-requisito etico'
    assert coverage({'A', 'B'}, ['75%'], {'A'}, 'exige 75 % ... 75%') == 2 / 3
    assert coverage(set(), [], set(), '') is None


def test_prf():
    assert prf({'a', 'b', 'x'}, {'a', 'b', 'c', 'd'}) == {'precisao': 0.667, 'revocacao': 0.5, 'f1': 0.571,
                                                         'acertos': 2, 'extraidas': 3, 'gabarito': 4}
    assert prf(set(), {'a'})['f1'] == 0.0


def test_summary_and_markdown():
    rows = [{'mode': m, 'hops': h, 'answerable': a, 'cobertura_contexto': c, 'fonte_recuperada': True,
             'cobertura_resposta': c, 'precisao_entidades': 1.0, 'nao_esperadas': [], 'citacoes': 2,
             'citacoes_validas': 2, 'segundos': 1.0, **({'exata': c == 1} if a else {'abstencao_correta': True})}
            for m in ('graphrag', 'vector_only') for h, a, c in ((1, True, 1.0), (3, True, 0.5), (0, False, None))]
    s = summarize(rows, use_llm=True)
    assert s['graphrag']['3+ saltos']['cobertura_contexto'] == 0.5
    assert s['vector_only']['Sem resposta']['abstencao_correta'] == 1.0
    md = markdown(s, {'data': 'hoje', 'modelo': 'm', 'embeddings': 'e', 'perguntas': 3})
    assert '| exatas | 0.50 | 0.50 |' in md


def test_gold_catalog_mimics_neo4j_score():
    cat = GoldCatalog([{'id': 'a', 'name': 'A', 'label': 'Disciplina'}], [[1.0, 0.0]])
    assert cat.vector_entities([1.0, 0.0])[0]['score'] == 1.0
    assert cat.vector_entities([-1.0, 0.0])[0]['score'] == 0.0


def test_infra_failures_are_excluded_from_means():
    base = {'mode': 'graphrag', 'hops': 1, 'answerable': True, 'cobertura_contexto': 1.0, 'fonte_recuperada': True}
    rows = [{**base, 'cobertura_resposta': 1.0, 'precisao_entidades': 1.0, 'nao_esperadas': [], 'citacoes': 1,
             'citacoes_validas': 1, 'segundos': 1.0, 'exata': True},
            {**base, 'cobertura_contexto': 0.0, 'falha_infra': True, 'resposta': 'Ollama indisponível (500)', 'segundos': 0.3}]
    s = summarize(rows, use_llm=True)['graphrag']['Todas com resposta']
    assert s['n'] == 1 and s['cobertura_contexto'] == 1.0
