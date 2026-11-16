"""Carrega o grafo-gabarito sintético (data/seed.json) e ingere o corpus (data/corpus).

Ordem: schema -> entidades (com embeddings) -> documentos e trechos (sem LLM) ->
relações, cada uma ligada ao trecho que contém a sua frase de evidência.
"""
import json
from pathlib import Path
from graph_store import GraphStore
from pipeline import ingest
from ollama_client import embed_many

DATA = Path(__file__).parent / 'data'


def load_seed():
    return json.loads((DATA / 'seed.json').read_text(encoding='utf8'))


def main(with_embeddings=True, reset=False):
    data = load_seed()
    store = GraphStore()
    try:
        if reset:
            store.run('MATCH (n) DETACH DELETE n')
        store.setup()
        vectors = [None] * len(data['entities'])
        if with_embeddings:
            try: vectors = embed_many([e['name'] for e in data['entities']])
            except Exception as exc: print('Sem vetores de entidades; a busca textual ainda funciona:', exc)
        for entity, vector in zip(data['entities'], vectors):
            store.put_entity({**entity, 'embedding': vector})
        for d in data['documents']:
            result = ingest(store, DATA / d['file'], d['version'], with_llm=False, with_embeddings=with_embeddings,
                            title=d['title'], doc_id=d['id'])
            for warning in sorted(set(result['warnings'])): print('Aviso:', warning)
            store.link_document_entity(d['entity'], d['id'])
        for edge in data['edges']:
            chunk_id = store.chunk_with_text(edge['document'], edge['evidence'])
            if not chunk_id:
                raise RuntimeError(f"Evidência não encontrada nos trechos de {edge['document']}: {edge['evidence']}")
            if not store.put_edge({**edge, 'evidence_id': chunk_id, 'source_type': 'synthetic_seed'}):
                raise RuntimeError(f"Relação do gabarito viola a assinatura de tipos: {edge}")
        print(f"Pronto: {len(data['entities'])} entidades, {len(data['edges'])} relações e "
              f"{len(data['documents'])} documentos sintéticos.")
    finally:
        store.close()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-embeddings', action='store_true')
    parser.add_argument('--reset', action='store_true', help='apaga todo o grafo antes da carga')
    args = parser.parse_args()
    main(with_embeddings=not args.no_embeddings, reset=args.reset)
