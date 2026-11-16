"""Streamlit UI: hybrid answer, sources, graph view, traversal, ingestion."""
import streamlit as st
from pathlib import Path
from tempfile import TemporaryDirectory
from config import DOMAIN
from graph_store import GraphStore
from retrieval import answer
from pipeline import ingest

st.set_page_config(page_title=DOMAIN['title'],page_icon='🕸️',layout='wide')
st.title(DOMAIN['title'])
st.caption(DOMAIN['warning'])

try:
    store=GraphStore()
    store.run('RETURN 1 AS ok')
except Exception as exc:
    st.error(f'Neo4j indisponível: {exc}. Inicie docker compose up -d e confira .env')
    st.stop()

consult,import_tab,graph_tab=st.tabs(['Perguntas','Ingestão de documentos','Explorar caminhos'])
with consult:
    question=st.text_input('Pergunte sobre os documentos e relações',placeholder='Ex.: Quais são os pré-requisitos ou dependências?')
    llm=st.checkbox('Gerar resposta com Ollama',value=True)
    if st.button('Consultar',disabled=not question.strip()):
        with st.spinner('Buscando evidências e percorrendo grafo...'):
            result=answer(store,question,use_llm=llm)
        st.markdown(result['answer'])
        st.subheader('Fontes textuais')
        for c in result['context']['chunks']:
            with st.expander(c['id']+' — '+str(c.get('locator',''))):st.write(c['text'])
        paths=result['context']['paths']
        st.subheader('Subgrafo de contexto — até 3 saltos')
        if paths:
            lines=['digraph G {','rankdir=LR;','node [shape=box, style=rounded];']
            for p in paths[:30]:
                a=p['source_name'].replace('"','\\"').replace('\n',' ')
                b=p['target_name'].replace('"','\\"').replace('\n',' ')
                rel=p['relation'].replace('"','')
                lines.append(f'"{a}" -> "{b}" [label="{rel}"];')
            lines.append('}')
            st.graphviz_chart('\n'.join(lines),use_container_width=True)
            st.dataframe(paths,use_container_width=True)
        else:st.info('Nenhum caminho foi recuperado para a pergunta.')
with import_tab:
    uploaded=st.file_uploader('Adicione um arquivo .pdf, .txt ou .md',type=['pdf','txt','md'])
    version=st.text_input('Versão do documento','1.0')
    llm_extraction=st.checkbox('Extrair entidades e relações com Ollama',value=True)
    vectors=st.checkbox('Gerar embeddings com Ollama',value=True)
    if uploaded and st.button('Ingerir arquivo'):
        with TemporaryDirectory() as directory:
            path=Path(directory)/Path(uploaded.name).name
            path.write_bytes(uploaded.read())
            with st.spinner('Processando documento...'):
                try:
                    result=ingest(store,path,version,with_llm=llm_extraction,with_embeddings=vectors)
                    st.success('Documento processado');st.json(result)
                except Exception as exc:st.error(f'Falha de ingestão: {exc}')
with graph_tab:
    st.write('Caminho mais curto entre dois IDs de entidades (até 8 relações).')
    a=st.text_input('ID de origem')
    b=st.text_input('ID de destino')
    if st.button('Buscar caminho',disabled=not a.strip() or not b.strip()):
        st.json(store.shortest_path(a,b))
