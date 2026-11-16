import re
from graph_view import subgraph_from_result, cited_entities, build_html, community_color


def result():
    return {
        'context': {
            'anchors': [{'id': 'pi', 'name': 'Projeto Integrador'}],
            'paths': [{'source': 'pi', 'target': 'bd', 'relation': 'EXIGE', 'evidence': 'PI exige BD.'}],
            'chains': [{'ids': ['pi', 'ed', 'alg'], 'relation': 'EXIGE', 'nodes': ['PI', 'ED', 'Alg'], 'anchor': 'PI'}],
            'shortest': [{'ids': ['pi', 'mat'], 'relations': ['INCLUI'], 'nodes': ['PI', 'Matriz']}],
        },
        'citations': {'valid': ['P1'], 'cited': ['P1'], 'invalid': []},
        'evidence_index': {'P1': {'ids': ['pi', 'ed', 'alg'], 'nodes': [], 'anchor': 'PI', 'relation': 'EXIGE'}},
    }


def test_subgraph_collects_paths_chains_and_shortest():
    nodes, edges = subgraph_from_result(result())
    assert nodes == {'pi', 'bd', 'ed', 'alg', 'mat'}
    assert {(e['source'], e['target']) for e in edges} == {('pi', 'bd'), ('pi', 'ed'), ('ed', 'alg'), ('pi', 'mat')}
    assert [e for e in edges if e['target'] == 'mat'][0]['dashed']


def test_cited_entities_and_html():
    assert cited_entities(result()) == {'pi', 'ed', 'alg'}
    details = [{'id': i, 'name': i.upper(), 'label': 'Disciplina', 'pagerank': 0.5, 'community': 3} for i in ['pi', 'bd']]
    html = build_html(details, subgraph_from_result(result())[1], anchors=['pi'], highlight=['pi'])
    assert 'vis-network' in html.lower() or 'vis.Network' in html
    assert 'PI exige BD.' in html
    assert not re.search(r'<(script|link)[^>]*(src|href)="(https?:|\.\./)', html)  # autocontido, sem internet
    assert community_color(None) == community_color(-1) != community_color(3)
