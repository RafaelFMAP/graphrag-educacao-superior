"""Run after seed: python smoke.py [--llm]. Requires Neo4j, optional Ollama."""
import argparse
import json
from pathlib import Path
from unittest.mock import patch
from graph_store import GraphStore
from retrieval import answer
from ollama_client import embed, chat


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--llm', action='store_true')
    options = parser.parse_args()
    data = json.loads((Path(__file__).parent/'data/seed.json').read_text(encoding='utf8'))
    store = GraphStore()
    try:
        store.run('CALL db.awaitIndexes(120)')
        count = store.run('MATCH (e:Entity) RETURN count(e) AS n')[0]['n']
        assert count >= len(data['entities']), count
        doc = data['documents'][0]
        rows = store.fulltext_chunks(doc['text'])
        assert rows, 'Text retrieval returned no evidence'
        edge = data['edges'][0]
        assert store.shortest_path(edge['source'], edge['target']), 'No graph path'
        assert store.evidence_for_relation(edge['source'], edge['target'], edge['type'])
        name = next(e['name'] for e in data['entities'] if e['id'] == edge['source'])
        assert store.nearby(name), 'Multi-hop retrieval returned no edges'
        with patch('retrieval.embed', return_value=[]):
            result = answer(store, doc['text'], use_llm=False)
        assert result['context']['chunks'], 'Answer has no text evidence'
        if options.llm:
            vector = embed(doc['text'])
            assert len(vector) == 768
            assert store.vector_chunks(vector), 'Vector search returned no chunks'
            assert chat('Responda em português de forma breve.', 'Diga olá.').strip()
        from streamlit.testing.v1 import AppTest
        ui = AppTest.from_file(str(Path(__file__).parent/'app.py')).run(timeout=30)
        assert not ui.exception, str(ui.exception)
        assert not ui.error, str(ui.error)
        assert len(ui.tabs) == 3, 'Expected three UI tabs'
        print('PASS: Streamlit UI, seed, indexes, text retrieval, graph traversal, provenance, answer' +
              (', embedding, vector search, LLM' if options.llm else ' (LLM not tested)'))
    finally:
        store.close()

if __name__ == '__main__':
    main()
