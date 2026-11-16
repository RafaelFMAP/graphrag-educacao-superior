"""Subgrafo interativo (pyvis / vis-network embutido no HTML, funciona sem internet).

Cor = comunidade (Leiden), tamanho = PageRank, borda grossa = entidade citada na
resposta, estrela = entidade-âncora da pergunta. Passe o mouse sobre nós e
arestas para ver detalhes e a frase de evidência.
"""
import re
from pyvis.network import Network

PALETTE = ['#4E79A7', '#F28E2B', '#59A14F', '#E15759', '#76B7B2', '#EDC948', '#B07AA1', '#FF9DA7', '#9C755F', '#BAB0AC']
NEUTRAL = '#9AA3AE'


def community_color(community):
    if community is None or community < 0:
        return NEUTRAL
    return PALETTE[int(community) % len(PALETTE)]


def subgraph_from_result(result):
    """Extrai (ids de nós, arestas) do contexto de retrieval.answer()."""
    context = result['context']
    edges = {}

    def add(s, t, rel, evidence=None, dashed=False):
        if s and t and s != t:
            edges.setdefault((s, t, rel), {'source': s, 'target': t, 'relation': rel, 'evidence': evidence, 'dashed': dashed})

    for p in context.get('paths', []):
        add(p['source'], p['target'], p['relation'], p.get('evidence'))
    for ch in context.get('chains', []):
        ids = ch.get('ids') or []
        for a, b in zip(ids, ids[1:]):
            add(a, b, ch['relation'])
    for sp in context.get('shortest', []):
        ids = sp.get('ids') or []
        for (a, b), rel in zip(zip(ids, ids[1:]), sp['relations']):
            add(a, b, rel, 'caminho mínimo (direção não indicada)', dashed=True)
    node_ids = {a['id'] for a in context.get('anchors', [])}
    for e in edges.values():
        node_ids.update((e['source'], e['target']))
    return node_ids, list(edges.values())


def cited_entities(result):
    """Ids de entidades presentes nas evidências [P#] citadas de forma válida."""
    check = result.get('citations') or {}
    index = result.get('evidence_index') or {}
    cited = set()
    for ref in check.get('valid', []):
        item = index.get(ref)
        if not isinstance(item, dict):
            continue
        if 'source' in item and 'target' in item:
            cited.update((item['source'], item['target']))
        cited.update(item.get('ids') or [])
    return cited


def build_html(details, edges, anchors=(), highlight=(), height=520):
    """`details`: lista de dicts id/name/label/pagerank/community (GraphStore.entity_details)."""
    net = Network(height=f'{height}px', width='100%', directed=True, cdn_resources='in_line',
                  bgcolor='#ffffff', font_color='#1f2937')
    max_pr = max((d.get('pagerank') or 0 for d in details), default=0) or 1
    anchors, highlight = set(anchors), set(highlight)
    known = set()
    for d in details:
        pr = d.get('pagerank') or 0
        title = (f"{d['name']}\nRótulo: {d.get('label')}\nPageRank: {pr}\nComunidade: {d.get('community')}"
                 + ('\nÂncora da pergunta' if d['id'] in anchors else '')
                 + ('\nCitada na resposta' if d['id'] in highlight else ''))
        fill = community_color(d.get('community'))
        color = {'background': fill, 'border': '#111827' if d['id'] in highlight else fill,
                 'highlight': {'background': fill, 'border': '#111827'}}
        net.add_node(d['id'], label=d['name'], title=title, color=color,
                     size=12 + 26 * pr / max_pr, shape='star' if d['id'] in anchors else 'dot',
                     borderWidth=4 if d['id'] in highlight else 1)
        known.add(d['id'])
    for e in edges:
        if e['source'] in known and e['target'] in known:
            net.add_edge(e['source'], e['target'], label=e['relation'], title=e.get('evidence') or e['relation'],
                         dashes=e.get('dashed', False), color='#6B7280', arrows='to')
    net.set_options("""{
      "physics": {"solver": "forceAtlas2Based", "stabilization": {"iterations": 150},
                  "forceAtlas2Based": {"gravitationalConstant": -60, "springLength": 120}},
      "edges": {"font": {"size": 10, "align": "middle"}, "smooth": {"type": "dynamic"}},
      "nodes": {"font": {"size": 13}},
      "interaction": {"hover": true, "navigationButtons": true, "tooltipDelay": 120}
    }""")
    return self_contained(net.generate_html(notebook=False))


def self_contained(html):
    """Remove do template do pyvis o link quebrado ../node_modules e o Bootstrap via CDN (só estético);
    o vis-network já vem embutido, então o grafo funciona sem internet."""
    html = re.sub(r'<script[^>]*src="(?:\.\./node_modules|https?://)[^"]*"[^>]*>\s*</script>', '', html, flags=re.S)
    html = re.sub(r'<link[^>]*href="(?:\.\./node_modules|https?://)[^"]*"[^>]*/?>', '', html, flags=re.S)
    return html
