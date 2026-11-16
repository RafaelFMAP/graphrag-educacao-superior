"""Streamlit UI: resposta fundamentada, subgrafo interativo, rastreabilidade, caminhos e ingestão."""
from pathlib import Path
from tempfile import TemporaryDirectory
import streamlit as st
import streamlit.components.v1 as components
from config import DOMAIN
from graph_store import GraphStore
from retrieval import answer
from pipeline import ingest
from graph_view import subgraph_from_result, cited_entities, build_html

st.set_page_config(page_title=DOMAIN['title'], page_icon='🕸️', layout='wide')
st.title(DOMAIN['title'])
st.caption(DOMAIN['warning'])


@st.cache_resource
def get_store():
    store = GraphStore()
    store.run('RETURN 1 AS ok')
    return store


try:
    store = get_store()
except Exception as exc:
    st.error(f'Neo4j indisponível: {exc}. Inicie docker compose up -d e confira .env')
    st.stop()


@st.cache_data(ttl=60)
def entity_catalog(_store):
    rows = _store.entity_candidates()
    return sorted(rows, key=lambda e: (e['label'], e['name']))


def describe(ref, item):
    if ref.startswith('T'):
        return 'Trecho', f"{item['id']} — {item.get('locator', '')}"
    if ref.startswith('C'):
        return 'Linha Cypher', '; '.join(f'{k}={v}' for k, v in item.items())
    if ref.startswith('G'):
        return 'Comunidade', f"{item['anchor']}: comunidade {item['community']} ({', '.join(item['members'])})"
    if 'nodes' in item and 'anchor' in item:
        return 'Cadeia', f"{item['relation']}: {' → '.join(item['nodes'])}"
    if 'nodes' in item:
        return 'Caminho mínimo', ' — '.join(item['nodes'])
    return 'Relação', f"{item['source_name']} -{item['relation']}-> {item['target_name']}"


def render_graph(details, edges, anchors=(), highlight=(), height=520):
    if not edges:
        st.info('Nenhuma relação do grafo foi usada como contexto.')
        return
    components.html(build_html(details, edges, anchors, highlight, height), height=height + 20, scrolling=False)
    st.caption('Cor = comunidade (Leiden) · tamanho = PageRank · ★ = entidade da pergunta · '
               'borda grossa = citada na resposta · tracejado = caminho mínimo. Passe o mouse para ver a evidência.')


def render_result(result):
    context = result['context']
    st.markdown(result['answer'])
    conf = result['confidence']
    check = result.get('citations')
    c1, c2, c3 = st.columns(3)
    c1.metric('Confiança', f"{conf['level']} ({conf['score']:.2f})")
    if check is not None:
        c2.metric('Citações válidas', f"{len(check['valid'])}/{len(check['cited'])}")
        if check['invalid']:
            c3.metric('Citações inválidas', ', '.join(check['invalid']))
    c1.caption(' · '.join(f'{k} {v:.2f}' for k, v in conf['signals'].items()) +
               (' · abstenção' if conf.get('abstention') else ''))
    if context.get('errors'):
        st.warning('Etapas com falha (a resposta usou as demais): ' + '; '.join(context['errors']))

    node_ids, edges = subgraph_from_result(result)
    details = store.entity_details(sorted(node_ids))
    anchors = [a['id'] for a in context.get('anchors', [])]
    cited = cited_entities(result)
    st.subheader('Subgrafo de contexto')
    render_graph(details, edges, anchors, cited)

    ev_tab, nodes_tab, cypher_tab, chunks_tab = st.tabs(['Evidências numeradas', 'Nós consultados', 'Consultas Cypher', 'Trechos'])
    valid = set((check or {}).get('valid', []))
    with ev_tab:
        rows = []
        for ref, item in result['evidence_index'].items():
            kind, text = describe(ref, item)
            rows.append({'id': ref, 'tipo': kind, 'evidência': text, 'citada': ref in valid})
        st.dataframe(rows, use_container_width=True, hide_index=True)
    with nodes_tab:
        role = {a['id']: f"âncora ({a.get('via', '')})" for a in context.get('anchors', [])}
        st.dataframe([{**d, 'papel': role.get(d['id'], 'vizinhança'), 'citada': d['id'] in cited}
                      for d in sorted(details, key=lambda d: -(d.get('pagerank') or 0))],
                     use_container_width=True, hide_index=True)
        st.caption(f"Relações seguidas na expansão: {', '.join(context.get('relations', [])) or '—'}")
    with cypher_tab:
        for q in context.get('queries', []):
            status = f" — {q['linhas']} linha(s)" if 'linhas' in q else ''
            st.markdown(f"**{q['origem']}**{status}")
            if q.get('erro'):
                st.caption(f"Erro: {q['erro']}")
            if q.get('query'):
                st.code(q['query'], language='cypher')
        cypher = result.get('cypher')
        if cypher:
            if cypher['rows']:
                st.dataframe(cypher['rows'], use_container_width=True, hide_index=True)
            if len(cypher['attempts']) > 1:
                with st.expander('Tentativas do Text2Cypher'):
                    for i, a in enumerate(cypher['attempts'], 1):
                        st.markdown(f"Tentativa {i}: {'ok' if not a['error'] else a['error']}")
                        st.code(a['query'] or '', language='cypher')
    with chunks_tab:
        for ref, item in result['evidence_index'].items():
            if ref.startswith('T'):
                with st.expander(f"[{ref}] {item['id']} — {item.get('locator', '')}" + (' ✓ citado' if ref in valid else '')):
                    st.write(item['text'])


consult, import_tab, graph_tab = st.tabs(['Perguntas', 'Ingestão de documentos', 'Explorar caminhos'])

with consult:
    question = st.text_input('Pergunte sobre os documentos e relações',
                             placeholder='Ex.: Quais disciplinas antecedem indiretamente Projeto Integrador?')
    o1, o2, o3 = st.columns([1, 1, 2])
    llm = o1.checkbox('Gerar resposta com Ollama', value=True)
    use_cypher = o2.checkbox('Text2Cypher', value=True, disabled=not llm)
    mode = o3.radio('Recuperação', ['GraphRAG híbrido', 'Somente vetorial (baseline)'], horizontal=True)
    if st.button('Consultar', disabled=not question.strip()):
        with st.spinner('Buscando evidências, percorrendo o grafo e gerando a resposta...'):
            st.session_state['last'] = answer(store, question, use_llm=llm, use_cypher=use_cypher,
                                              mode='graphrag' if mode.startswith('GraphRAG') else 'vector_only')
    if st.session_state.get('last'):
        render_result(st.session_state['last'])

with import_tab:
    uploaded = st.file_uploader('Adicione um arquivo .pdf, .txt ou .md', type=['pdf', 'txt', 'md'])
    version = st.text_input('Versão do documento', '1.0')
    llm_extraction = st.checkbox('Extrair entidades e relações com Ollama', value=True)
    vectors = st.checkbox('Gerar embeddings com Ollama', value=True)
    if uploaded and st.button('Ingerir arquivo'):
        with TemporaryDirectory() as directory:
            path = Path(directory) / Path(uploaded.name).name
            path.write_bytes(uploaded.read())
            with st.spinner('Processando documento...'):
                try:
                    result = ingest(store, path, version, with_llm=llm_extraction, with_embeddings=vectors)
                    try:
                        from analytics import run_analytics
                        result['algoritmos_de_grafo'] = run_analytics(store)
                    except Exception as exc:
                        result['warnings'].append(f'Algoritmos de grafo não recalculados: {exc}')
                    entity_catalog.clear()
                    st.success(f"Documento {result['document']} processado")
                    m = st.columns(4)
                    for col, key, label in zip(m, ['chunks', 'entities', 'relations', 'mentions'],
                                               ['Trechos', 'Entidades novas', 'Relações', 'Menções']):
                        col.metric(label, result[key])
                    if result['resolved']:
                        st.markdown('**Resolução de entidades**')
                        st.dataframe(result['resolved'], use_container_width=True, hide_index=True)
                    if result['rejected']:
                        st.markdown('**Relações recusadas pela assinatura de tipos**')
                        st.write(result['rejected'])
                    for w in sorted(set(result['warnings'])):
                        st.warning(w)
                except Exception as exc:
                    st.error(f'Falha de ingestão: {exc}')

with graph_tab:
    catalog = entity_catalog(store)
    names = {f"{e['name']} ({e['label']})": e['id'] for e in catalog}
    st.write('Caminho mais curto entre duas entidades (até 6 relações, atravessando qualquer tipo de relação).')
    options = list(names)
    c1, c2 = st.columns(2)
    a = c1.selectbox('Origem', options, index=next((i for i, o in enumerate(options) if o.startswith('Projeto Integrador')), 0))
    b = c2.selectbox('Destino', options, index=next((i for i, o in enumerate(options) if o.startswith('Algoritmos')), 0))
    if st.button('Buscar caminho', disabled=not options or a == b):
        path = store.shortest_path_ids(names[a], names[b], max_degree=10_000)
        if not path:
            st.info('Não há caminho entre as entidades escolhidas.')
        else:
            p = path[0]
            st.markdown(' → '.join(f'**{n}** _{r}_' for n, r in zip(p['nodes'], p['relations'] + [''])))
            edges = [{'source': s, 'target': t, 'relation': r, 'evidence': None}
                     for (s, t), r in zip(zip(p['ids'], p['ids'][1:]), p['relations'])]
            render_graph(store.entity_details(p['ids']), edges, anchors=[p['ids'][0], p['ids'][-1]], height=380)
    with st.expander('Entidades mais centrais (PageRank) e comunidades (Leiden)'):
        st.dataframe(store.run("""MATCH (n:Entity) RETURN n.name AS entidade, n.kind AS rótulo,
            round(coalesce(n.pagerank, 0), 3) AS pagerank, n.community AS comunidade
            ORDER BY pagerank DESC LIMIT 15"""), use_container_width=True, hide_index=True)
