"""GraphRAG híbrido: vetor + fulltext + travessia Cypher multi-hop + algoritmos de grafo + Text2Cypher.

Fluxo de `answer()` no modo 'graphrag':
  1. Ligação de entidades: nomes e aliases citados na pergunta; na falta deles,
     busca vetorial (entity_vector) e fulltext (entity_text) fundidas por RRF.
  2. Trechos: busca vetorial (chunk_vector) e fulltext (chunk_text) fundidas por RRF,
     mais os trechos de procedência das relações recuperadas.
  3. Grafo: expansão de 1 a 3 saltos a partir das âncoras, restrita às relações
     sugeridas pela pergunta, sem atravessar hubs e ordenada por distância e PageRank;
     caminhos mínimos entre pares de âncoras; comunidade (Leiden/Louvain) das âncoras.
  4. Text2Cypher: consulta de leitura gerada pelo LLM, validada e executada.
  5. Geração com contexto numerado ([T#] trechos, [P#] caminhos, [C#] linhas Cypher,
     [G#] comunidades); verificação das citações e cálculo da confiança.

O modo 'vector_only' é o baseline do RAG vetorial puro, usado na avaliação.
"""
import re
from itertools import combinations
from ollama_client import chat, embed
from config import DOMAIN
from pipeline import find_mentions
import confidence
import text2cypher

RRF_K = 60
MAX_CHUNKS = 6
MAX_PATHS = 25
HUB_DEGREE = 15
# Relações dirigidas em que vale explicitar cadeias completas no contexto
CHAIN_RELATIONS = ['EXIGE', 'SUBSTITUI', 'EQUIVALE_A']

# Palavras da pergunta -> relações que a expansão deve seguir (planejamento lógico simples, estilo KAG)
INTENTS = [
    (r'pr[ée]-?requisit|exig|antecede|anterior(?:es)? a|depend|cadeia|antes de|cursar', ['EXIGE']),
    (r'equival|migra', ['EQUIVALE_A']),
    (r'compet[êe]ncia|desenvolv', ['DESENVOLVE']),
    (r'matriz|inclu|grade|curr[íi]cul|per[íi]odo', ['INCLUI', 'ADOTA', 'SUBSTITUI']),
    (r'artigo|regulament|norma|regra', ['POSSUI', 'DEFINE']),
    (r'atividades? complementar|monitoria|inicia[çc][ãa]o|maratona|extens[ãa]o', ['DEFINE', 'POSSUI']),
    (r'documento|fundament|defin|ppc', ['DEFINE']),
    (r'oferec|campus|universidade|institui', ['OFERECE', 'POSSUI']),
    (r'substitu|vers[ãa]o|posterior|antiga|nova', ['SUBSTITUI', 'DEFINE']),
]

# Leitura em linguagem natural da direção de cada relação, para modelos pequenos não a inverterem
RELATION_GLOSS = {'EXIGE': ' (tem como pré-requisito)', 'EQUIVALE_A': ' (equivale a)', 'INCLUI': ' (inclui a disciplina)',
                  'DESENVOLVE': ' (desenvolve a competência)', 'ADOTA': ' (adota a matriz)', 'DEFINE': ' (define)',
                  'SUBSTITUI': ' (substitui)', 'OFERECE': ' (oferece)', 'POSSUI': ' (possui)', 'PERTENCE_A': ' (pertence a)'}

NO_EVIDENCE = 'Não há evidência recuperada para responder com segurança. Faça a ingestão de documentos ou reformule a busca.'


def intent_relations(question):
    found = []
    for pattern, relations in INTENTS:
        if re.search(pattern, question, re.I):
            found += [r for r in relations if r not in found]
    return found or list(DOMAIN['relations'])


def rrf(*rankings, k=RRF_K):
    """Reciprocal Rank Fusion: soma 1/(k + posição) de cada lista; devolve ids ordenados."""
    scores = {}
    for ranking in rankings:
        for pos, ident in enumerate(ranking):
            scores[ident] = scores.get(ident, 0.0) + 1.0 / (k + pos + 1)
    return sorted(scores, key=lambda i: -scores[i])


def _safe(fn, *args, default=None, errors=None, label=''):
    try:
        return fn(*args)
    except Exception as exc:
        if errors is not None:
            errors.append(f'{label}: {str(exc).splitlines()[0][:200]}')
        return [] if default is None else default


def link_entities(store, question, vector, errors):
    """Âncoras: menções explícitas primeiro; senão, vetor + fulltext de entidades."""
    catalog = _safe(store.entity_candidates, default=[], errors=errors, label='catálogo')
    by_id = {e['id']: e for e in catalog}
    mentioned = find_mentions(question, catalog)
    if mentioned:
        return [{**by_id[i], 'via': 'menção'} for i in mentioned[:5]]
    vec_hits = _safe(store.vector_entities, vector, 5, errors=errors, label='vetor de entidades') if vector else []
    ft_hits = _safe(store.fulltext_entities, question, 5, errors=errors, label='fulltext de entidades')
    ranked = rrf([h['id'] for h in vec_hits if h['score'] >= 0.80], [h['id'] for h in ft_hits])
    return [{**by_id[i], 'via': 'vetor/fulltext'} for i in ranked[:3] if i in by_id]


def retrieve(store, question, mode='graphrag'):
    errors = []
    vector = _safe(embed, question, default=None, errors=errors, label='embedding')
    vec_chunks = _safe(store.vector_chunks, vector, 8, errors=errors, label='vetor de trechos') if vector else []
    context = {'mode': mode, 'chunks': [], 'paths': [], 'chains': [], 'shortest': [], 'communities': [], 'anchors': [],
               'relations': [], 'queries': [], 'errors': errors,
               'best_vector_score': max((c['score'] for c in vec_chunks), default=None)}
    if mode == 'vector_only':
        context['chunks'] = vec_chunks[:MAX_CHUNKS]
        return context

    ft_chunks = _safe(store.fulltext_chunks, question, 8, errors=errors, label='fulltext de trechos')
    rows = {c['id']: c for c in vec_chunks + ft_chunks}
    fused = rrf([c['id'] for c in vec_chunks], [c['id'] for c in ft_chunks])

    anchors = link_entities(store, question, vector, errors)
    relations = intent_relations(question)
    context['anchors'] = anchors; context['relations'] = relations
    anchor_ids = [a['id'] for a in anchors]
    if anchor_ids:
        context['paths'] = _safe(store.expand, anchor_ids, relations, MAX_PATHS, HUB_DEGREE, errors=errors, label='expansão')
        context['queries'].append({'origem': 'Expansão multi-hop (modelo fixo)', 'query': store.expand_query(relations)})
        if len(context['paths']) == 0 and relations != list(DOMAIN['relations']):
            context['paths'] = _safe(store.expand, anchor_ids, list(DOMAIN['relations']), MAX_PATHS, HUB_DEGREE, errors=errors, label='expansão ampla')
        for relation in [r for r in relations if r in CHAIN_RELATIONS and len(relations) <= 4]:
            for outgoing in (True, False):
                context['chains'] += _safe(store.chains, anchor_ids, relation, outgoing, errors=errors, label='cadeias')
        if context['chains']:
            # as cadeias já cobrem os saltos longos; dos caminhos ficam só as relações diretas
            context['paths'] = [p for p in context['paths'] if p.get('hops') == 1]
        for a, b in list(combinations(anchor_ids, 2))[:3]:
            path = _safe(store.shortest_path_ids, a, b, HUB_DEGREE, errors=errors, label='caminho mínimo')
            if path: context['shortest'].append(path[0])
        context['communities'] = _safe(store.communities_of, anchor_ids, errors=errors, label='comunidades')
    # Trechos de procedência das relações mais relevantes entram depois dos trechos fundidos
    evidence_ids = [p['evidence_id'] for p in context['paths'][:12] if p.get('evidence_id')]
    missing = [i for i in dict.fromkeys(evidence_ids) if i not in rows]
    for c in _safe(store.chunks_by_id, missing[:3], errors=errors, label='trechos de evidência'):
        rows[c['id']] = c
    ordered = fused[:MAX_CHUNKS - min(2, len(missing))] + [i for i in missing[:2] if i in rows]
    context['chunks'] = [rows[i] for i in ordered]
    return context


def format_context(context, cypher=None):
    """Numera as evidências; devolve (texto, ids válidos, mapa id -> item)."""
    lines = []; index = {}
    for n, c in enumerate(context['chunks'], 1):
        index[f'T{n}'] = c
        lines.append(f"[T{n}] (trecho {c['id']}) {c['text'][:900]}")
    # Cadeias dirigidas primeiro: são o raciocínio multi-hop já resolvido pelo grafo
    for n, ch in enumerate(context.get('chains', []), 1):
        index[f'P{n}'] = ch
        gloss = RELATION_GLOSS.get(ch['relation'], '').strip(' ()')
        kind = 'a partir de' if ch['outgoing'] else 'até'
        lines.append(f"[P{n}] Cadeia {ch['relation']} {kind} {ch['anchor']}: {' → '.join(ch['nodes'])} "
                     f"(cada seta significa '{gloss}'; {ch['hops']} salto(s))")
    offset = len(context.get('chains', []))
    for n, p in enumerate(context['paths'], offset + 1):
        index[f'P{n}'] = p
        gloss = RELATION_GLOSS.get(p['relation'], '')
        lines.append(f"[P{n}] {p['source_name']} {p['relation']}{gloss} {p['target_name']} (distância {p.get('hops', '?')} da pergunta)")
    offset += len(context['paths'])
    for n, s in enumerate(context['shortest'], offset + 1):
        index[f'P{n}'] = s
        chain = s['nodes'][0]
        for rel, node in zip(s['relations'], s['nodes'][1:]):
            chain += f' -{rel}- {node}'
        lines.append(f'[P{n}] Caminho mínimo: {chain}')
    for n, g in enumerate(context['communities'], 1):
        index[f'G{n}'] = g
        lines.append(f"[G{n}] Comunidade {g['community']} (algoritmo de comunidades) de {g['anchor']}: membros centrais {', '.join(g['members'])}")
    if cypher and cypher.get('rows'):
        for n, row in enumerate(cypher['rows'][:25], 1):
            index[f'C{n}'] = row
            lines.append(f'[C{n}] ' + '; '.join(f'{k}={v}' for k, v in row.items()))
    return '\n'.join(lines), set(index), index


SYSTEM = (f"Você é um assistente especializado em {DOMAIN['domain']}. "
          "Responda em português, exclusivamente com base nas EVIDÊNCIAS numeradas. "
          "Depois de cada afirmação, cite entre colchetes os identificadores que a sustentam, por exemplo [T1] ou [P2]. "
          "Não cite identificadores que não aparecem nas evidências. "
          "Se as evidências não bastarem, escreva 'Não há evidência suficiente' e explique o que falta. "
          "Não invente normas, decisões nem fatos, e não decida casos individuais de estudantes: indique a regra e quem decide. "
          + DOMAIN['warning'])


def answer(store, question, use_llm=True, mode='graphrag', use_cypher=True):
    context = retrieve(store, question, mode)
    cypher = None
    if mode == 'graphrag' and use_llm and use_cypher:
        cypher = text2cypher.generate_and_run(store, question, context['anchors'],
                                               lambda system, prompt: chat(system, prompt, options={'temperature': 0}))
        context['queries'].insert(0, {'origem': 'Text2Cypher (LLM, validada, só leitura)',
                                      'query': cypher['query'] or (cypher['attempts'][-1]['query'] if cypher['attempts'] else ''),
                                      'linhas': len(cypher['rows']), 'erro': cypher['error']})
    evidence, valid_ids, index = format_context(context, cypher)
    result = {'context': context, 'cypher': cypher, 'evidence_index': index, 'citations': None}
    nodes = {}
    for a in context['anchors']:
        nodes[a['id']] = {'id': a['id'], 'name': a['name'], 'label': a['label'], 'papel': 'âncora'}
    for p in context['paths']:
        for side in ('source', 'target'):
            nodes.setdefault(p[side], {'id': p[side], 'name': p[f'{side}_name'], 'label': p.get(f'{side}_label'), 'papel': 'vizinhança'})
    result['nodes'] = list(nodes.values())
    cypher_rows = len(cypher['rows']) if cypher else None
    if not evidence:
        result['answer'] = NO_EVIDENCE
        result['confidence'] = confidence.score(None, None, 0, 0, cypher_rows)
        return result
    if not use_llm:
        result['answer'] = 'Evidências recuperadas (geração por LLM desativada). Consulte os trechos e os caminhos abaixo.'
        result['confidence'] = confidence.score(None, context['best_vector_score'], len(context['anchors']),
                                                len(context['paths']), cypher_rows)
        return result
    try:
        text = chat(SYSTEM, f'EVIDÊNCIAS:\n{evidence}\n\nPergunta: {question}\n'
                            'Responda de forma direta e cite, após cada afirmação, os identificadores [T#], [P#], [C#] ou [G#] usados.',
                    options={'temperature': 0})
    except Exception as exc:
        text = f'Ollama indisponível ({exc}). Evidências recuperadas abaixo; não foi gerada resposta.'
    check = confidence.verify_citations(text, valid_ids)
    if check['invalid']:
        text += f"\n\n> ⚠️ Citações sem correspondência no contexto foram ignoradas: {', '.join(check['invalid'])}."
    if not check['valid'] and not confidence.is_abstention(text):
        text += '\n\n> ⚠️ A resposta não citou evidências válidas; trate-a como não verificada.'
    result['answer'] = text
    result['citations'] = check
    result['confidence'] = confidence.score(check, context['best_vector_score'], len(context['anchors']),
                                            len(context['paths']), cypher_rows, confidence.is_abstention(text))
    return result
