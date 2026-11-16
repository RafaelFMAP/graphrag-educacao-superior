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
