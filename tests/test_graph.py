import pytest
from graph_store import GraphStore

class FakeDriver:
    def close(self): pass

def test_reject_unknown_label():
    store=GraphStore(driver=FakeDriver())
    with pytest.raises(ValueError):store.put_entity({'id':'x','name':'X','label':'Hack'})

def test_reject_unknown_relation():
    store=GraphStore(driver=FakeDriver())
    with pytest.raises(ValueError):store.put_edge({'source':'a','target':'b','type':'HACK'})


def test_seed_respects_relation_signatures():
    import json
    from pathlib import Path
    from config import DOMAIN
    seed = json.loads((Path(__file__).parent.parent / 'data' / 'seed.json').read_text(encoding='utf8'))
    labels = {e['id']: e['label'] for e in seed['entities']}
    assert set(DOMAIN['relation_signatures']) == set(DOMAIN['relations'])
    for edge in seed['edges']:
        sources, targets = DOMAIN['relation_signatures'][edge['type']]
        assert labels[edge['source']] in sources and labels[edge['target']] in targets, edge
