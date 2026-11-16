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
