"""Qualidade do pipeline Text-to-Graph (NER/RE + resolução de entidades) contra o grafo-gabarito.

Para cada documento do corpus, extrai entidades e relações trecho a trecho com
o LLM (sem gravar no banco) e compara com o gabarito daquele documento:

  entidades  precisão/revocação/F1 dos ids SEM resolução (só canonicalização do nome)
             e COM a resolução de entidades (alias, sigla, fuzzy, vetor, rótulo divergente)
  relações   precisão/revocação/F1 das triplas (origem, tipo, destino) após a resolução,
             antes e depois do filtro de assinatura de tipos (restrições semânticas)
  resolução  quantas entidades extraídas com id diferente do gabarito a resolução corrigiu

A resolução usa um catálogo em memória com as entidades do gabarito e os
embeddings dos seus nomes (mesmo score (1 + cos) / 2 do Neo4j).

    python evaluate_extraction.py            # requer Ollama
Saída: docs/resultados/extracao.json e docs/resultados/extracao.md
"""
import json
import math
import time
from pathlib import Path
from config import DOMAIN, OLLAMA_MODEL
from entity_resolution import EntityResolver
from ollama_client import embed, embed_many
from pipeline import chunks_of, extract_graph

ROOT = Path(__file__).parent
OUT = ROOT / 'docs' / 'resultados'


class GoldCatalog:
    """Imita GraphStore.entity_candidates/vector_entities sobre o gabarito, sem Neo4j."""
    def __init__(self, entities, vectors):
        self.entities = entities
        self.vectors = vectors

    def entity_candidates(self, label=None):
        return [e for e in self.entities if label is None or e['label'] == label]

    def vector_entities(self, embedding, limit=5):
        def cos(a, b):
            return sum(x * y for x, y in zip(a, b)) / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))
        scored = [{**e, 'score': (1 + cos(embedding, v)) / 2} for e, v in zip(self.entities, self.vectors)]
        return sorted(scored, key=lambda e: -e['score'])[:limit]


def prf(found, gold):
    tp = len(found & gold)
    p = tp / len(found) if found else 0.0
    r = tp / len(gold) if gold else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {'precisao': round(p, 3), 'revocacao': round(r, 3), 'f1': round(f, 3), 'acertos': tp,
            'extraidas': len(found), 'gabarito': len(gold)}


def main():
    seed = json.loads((ROOT / 'data' / 'seed.json').read_text(encoding='utf8'))
    labels = {e['id']: e['label'] for e in seed['entities']}
    catalog = GoldCatalog(seed['entities'], embed_many([e['name'] for e in seed['entities']]))
    totals = {'raw': [set(), set()], 'resolved': [set(), set()], 'rel': [set(), set()], 'rel_sig': [set(), set()]}
    report = {'documentos': {}, 'resolucao': {}, 'falhas': []}
    t0 = time.time()
    for doc in seed['documents']:
        text = (ROOT / 'data' / doc['file']).read_text(encoding='utf8')
        gold_entities = {e['id'] for e in seed['entities'] if e['name'] in text}
        gold_edges = {(e['source'], e['type'], e['target']) for e in seed['edges'] if e['document'] == doc['id']}
        resolver = EntityResolver(catalog, embed_fn=embed)
        raw, resolved, rels, rels_sig = set(), set(), set(), set()
        for i, chunk in enumerate(chunks_of(text)):
            try:
                entities, edges = extract_graph(chunk)
            except Exception as exc:
                report['falhas'].append(f"{doc['id']} trecho {i}: {exc}")
                continue
            mapping = {}
            for e in entities:
                raw.add(e['id'])
                rid, method, _ = resolver.resolve(e['name'], e['label'])
                mapping[e['id']] = rid
                resolved.add(rid)
                if rid != e['id']:
                    key = f"{method}: {'corrigida' if rid in gold_entities else 'fundida errado'}"
                    report['resolucao'][key] = report['resolucao'].get(key, 0) + 1
                if method == 'novo':
                    resolver.remember(rid, e['name'], e['label'])
                    labels.setdefault(rid, e['label'])
            for edge in edges:
                triple = (mapping[edge['source']], edge['type'], mapping[edge['target']])
                rels.add(triple)
                sources, targets = DOMAIN['relation_signatures'][edge['type']]
                if labels.get(triple[0]) in sources and labels.get(triple[2]) in targets:
                    rels_sig.add(triple)
            print(f"{doc['id']} trecho {i}: {len(entities)} entidades, {len(edges)} relações", flush=True)
        for key, found, gold in [('raw', raw, gold_entities), ('resolved', resolved, gold_entities),
                                 ('rel', rels, gold_edges), ('rel_sig', rels_sig, gold_edges)]:
            totals[key][0] |= {(doc['id'], x) for x in found}
            totals[key][1] |= {(doc['id'], x) for x in gold}
        report['documentos'][doc['id']] = {
            'entidades_sem_resolucao': prf(raw, gold_entities), 'entidades_com_resolucao': prf(resolved, gold_entities),
            'relacoes': prf(rels, gold_edges), 'relacoes_com_assinatura': prf(rels_sig, gold_edges),
            'relacoes_erradas_exemplos': sorted(' '.join(t) for t in rels_sig - gold_edges)[:10]}
    report['total'] = {
        'entidades_sem_resolucao': prf(*totals['raw']), 'entidades_com_resolucao': prf(*totals['resolved']),
        'relacoes': prf(*totals['rel']), 'relacoes_com_assinatura': prf(*totals['rel_sig'])}
    report['meta'] = {'data': time.strftime('%Y-%m-%d %H:%M'), 'modelo': OLLAMA_MODEL, 'segundos': round(time.time() - t0)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'extracao.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    names = {'entidades_sem_resolucao': 'Entidades (só canonicalização)', 'entidades_com_resolucao': 'Entidades (com resolução)',
             'relacoes': 'Relações (evidência literal)', 'relacoes_com_assinatura': 'Relações (+ assinatura de tipos)'}
    md = [f"# Qualidade da extração (Text-to-Graph) — {report['meta']['data']}", '',
          f"Modelo: `{OLLAMA_MODEL}` · {len(seed['documents'])} documentos · {report['meta']['segundos']} s.", '',
          '| Conjunto | Precisão | Revocação | F1 | Acertos / extraídas / gabarito |', '|---|---|---|---|---|']
    for k, label in names.items():
        m = report['total'][k]
        md.append(f"| {label} | {m['precisao']:.2f} | {m['revocacao']:.2f} | {m['f1']:.2f} | {m['acertos']} / {m['extraidas']} / {m['gabarito']} |")
    md += ['', '**Decisões da resolução de entidades** (ids extraídos diferentes do id canônico final):', '']
    md += [f'- {k}: {v}' for k, v in sorted(report['resolucao'].items())] or ['- nenhuma']
    if report['falhas']:
        md += ['', f"Trechos com falha de extração: {len(report['falhas'])}."]
    (OUT / 'extracao.md').write_text('\n'.join(md) + '\n', encoding='utf8')
    print('\n'.join(md))


if __name__ == '__main__':
    main()
