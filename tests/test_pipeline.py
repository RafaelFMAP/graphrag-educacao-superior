from pipeline import canonical, chunks_of, extract_graph
from unittest.mock import patch
import json

def test_canonical():
    assert canonical('Estruturas de Dados')=='estruturas-de-dados'

def test_chunk_overlap():
    chunks=chunks_of('a'*1200,size=500,overlap=100)
    assert len(chunks)==3
    assert chunks[0][-100:]==chunks[1][:100]

def test_empty():
    assert chunks_of('   ')==[]

def test_relation_requires_literal_evidence():
    # A hallucinated relationship is rejected even if both entities occur.
    from config import DOMAIN
    labels=DOMAIN['labels'];relation=DOMAIN['relations'][0]
    text='Elemento Alfa e Elemento Beta são citados aqui.'
    payload={'entities':[{'id':'a','name':'Elemento Alfa','label':labels[0]},
             {'id':'b','name':'Elemento Beta','label':labels[1]}],
             'edges':[{'source':'a','target':'b','type':relation,'evidence':'frase que não aparece'}]}
    with patch('pipeline.chat',return_value=json.dumps(payload)):
        entities,edges=extract_graph(text)
    assert len(entities)==2 and not edges

import pytest

@pytest.mark.parametrize('size,overlap', [(0,0), (-1,0), (10,10), (10,11), (10,-1)])
def test_invalid_chunk_parameters(size, overlap):
    with pytest.raises(ValueError):
        chunks_of('texto', size=size, overlap=overlap)


from pipeline import document_id, find_mentions


def test_chunks_keep_paragraphs_and_heading():
    text = '# Seção\n\n' + '\n\n'.join(f'Parágrafo {i} ' + 'x' * 80 for i in range(10))
    chunks = chunks_of(text, size=300, overlap=50)
    assert len(chunks) > 1
    for c in chunks:
        assert c.startswith('# Seção')
        assert all(p.startswith(('Parágrafo', '# Seção')) for p in c.split('\n\n'))


def test_long_paragraph_falls_back_to_fixed_windows():
    chunks = chunks_of('curto\n\n' + 'y' * 700, size=300, overlap=50)
    assert chunks[0] == 'curto' and all(len(c) <= 300 for c in chunks)


def test_document_id_does_not_repeat_version():
    assert document_id('ppc-2026', '2026') == 'ppc-2026'
    assert document_id('Regulamento', '1.0') == 'regulamento-1-0'


def test_mentions_prefer_longest_name():
    entities = [{'id': 'bd', 'name': 'Banco de Dados', 'aliases': ['BD']},
                {'id': 'bda', 'name': 'Banco de Dados Avançado', 'aliases': []},
                {'id': 'ia', 'name': 'Inteligência Artificial', 'aliases': ['IA']}]
    assert find_mentions('Banco de Dados Avançado exige BD.', entities) == ['bda', 'bd']
    assert find_mentions('A media e a via não são IA? Sim, IA.', entities) == ['ia']
    assert find_mentions('nada aqui', entities) == []


def test_seed_evidence_is_literal_in_corpus():
    import json
    from pathlib import Path
    data_dir = Path(__file__).parent.parent / 'data'
    seed = json.loads((data_dir / 'seed.json').read_text(encoding='utf8'))
    texts = {d['id']: (data_dir / d['file']).read_text(encoding='utf8') for d in seed['documents']}
    for edge in seed['edges']:
        assert edge['evidence'] in texts[edge['document']]
        # cada evidência cabe num trecho, então o seed sempre encontra o chunk de origem
        assert any(edge['evidence'] in c for c in chunks_of(texts[edge['document']]))


def test_extraction_cleans_names_and_rejects_reserved():
    from pipeline import clean_name
    assert clean_name('Banco de Dados (Matriz 2026)') == 'Banco de Dados'
    assert clean_name('"Algoritmos".') == 'Algoritmos'
    text = 'Banco de Dados (Matriz 2026) equivale a Banco de Dados I (Matriz 2022). EXIGE'
    payload = {'entities': [{'id': 'a', 'name': 'Banco de Dados (Matriz 2026)', 'label': 'Disciplina'},
                            {'id': 'b', 'name': 'Banco de Dados I (Matriz 2022)', 'label': 'Disciplina'},
                            {'id': 'c', 'name': 'EXIGE', 'label': 'Regulamento'}],
               'edges': [{'source': 'a', 'target': 'b', 'type': 'EQUIVALE_A',
                          'evidence': 'Banco de Dados (Matriz 2026) equivale a Banco de Dados I (Matriz 2022).'}]}
    with patch('pipeline.chat', return_value=json.dumps(payload)):
        entities, edges = extract_graph(text)
    assert [e['id'] for e in entities] == ['banco-de-dados', 'banco-de-dados-i']
    assert edges[0]['source'] == 'banco-de-dados' and edges[0]['target'] == 'banco-de-dados-i'
