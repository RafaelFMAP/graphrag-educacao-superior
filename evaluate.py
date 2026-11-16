"""Basic retrieval evaluation against manually reviewed ground truth."""
import json
from pathlib import Path
from graph_store import GraphStore
from retrieval import retrieve

def main():
    items=json.loads((Path(__file__).parent/'data'/'questions.json').read_text(encoding='utf8'))
    reviewed=[x for x in items if not x.get('needs_manual_review',True)]
    if not reviewed:
        print('Avaliação bloqueada: revise as 20 perguntas em data/questions.json, preencha expected_sources e defina needs_manual_review=false. Não há métricas fictícias.')
        return
    store=GraphStore()
    try:
        successes=0
        for item in reviewed:
            result=retrieve(store,item['question'])
            ids={x['id'] for x in result['chunks']}
            expected=set(item['expected_sources'])
            hit=bool(expected and any(any(doc in cid for doc in expected) for cid in ids))
            successes+=int(hit)
            print(('OK' if hit else 'MISS'),item['question'])
        print('Recall@10 por pergunta:',round(successes/len(reviewed),3))
    finally:store.close()
if __name__=='__main__':main()
