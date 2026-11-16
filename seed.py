"""Load reproducible synthetic demonstration graph, with clear provenance markers."""
import json
from pathlib import Path
from graph_store import GraphStore
from pipeline import canonical
from ollama_client import embed

def main(with_embeddings=True):
    data=json.loads((Path(__file__).parent/'data'/'seed.json').read_text(encoding='utf8'))
    store=GraphStore()
    try:
        store.setup()
        for e in data['entities']:store.put_entity(e)
        for d in data['documents']:
            store.put_document({'id':d['id'],'title':d['title'],'version':d['version'],'origin':'dados sintéticos'})
            chunk={'id':'seed-'+d['id'],'doc_id':d['id'],'text':d['text'],'locator':'documento demonstrativo','embedding':None}
            try:
                if with_embeddings: chunk['embedding']=embed(d['text'])
            except Exception as exc:print('Sem vetor, busca textual ainda funciona:',exc)
            store.put_chunk(chunk)
        for e in data['edges']:
            e={**e,'source_type':'synthetic_seed','evidence_id':'seed-'+data['documents'][0]['id']}
            store.put_edge(e)
        for e in data['entities']:
            for d in data['documents']:
                if e['name'].casefold() in d['text'].casefold():store.link_mention('seed-'+d['id'],e['id'])
        print(f"Pronto: {len(data['entities'])} entidades e {len(data['edges'])} relações sintéticas.")
    finally:store.close()
if __name__=='__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-embeddings', action='store_true')
    main(with_embeddings=not parser.parse_args().no_embeddings)
