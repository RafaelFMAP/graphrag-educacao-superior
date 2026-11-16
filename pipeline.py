"""Text -> chunks -> entities/relation extraction -> Neo4j with provenance."""
import json
import re
import unicodedata
from pathlib import Path
from pypdf import PdfReader
from config import DOMAIN
from ollama_client import chat, embed

def canonical(text):
    text=unicodedata.normalize('NFKD',text.lower())
    text=''.join(c for c in text if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+','-',text).strip('-')[:90]

def load_document(path):
    path=Path(path)
    if path.suffix.lower()=='.pdf':
        reader=PdfReader(str(path))
        return [(f"página {i+1}",page.extract_text() or '') for i,page in enumerate(reader.pages)]
    if path.suffix.lower() in ('.txt','.md'):
        return [('texto',path.read_text(encoding='utf8'))]
    raise ValueError('Somente PDF, TXT ou MD são aceitos.')

def chunks_of(text, size=900, overlap=140):
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError('Use size > 0 e 0 <= overlap < size')
    if not text.strip(): return []
    # fixed-size character chunks for reproducibility
    out=[];start=0
    while start<len(text):
        stop=min(len(text),start+size)
        out.append(text[start:stop])
        if stop==len(text):break
        start=stop-overlap
    return out

def extract_graph(text):
    """NER/RE via LLM; strict whitelist and evidence-string validation.
    Output is rejected if relationships have no literal supporting substring.
    """
    schema=f"Labels: {DOMAIN['labels']}. Relations: {DOMAIN['relations']}."
    instruction=("Extraia entidades e relações somente se forem sustentadas pelo TEXTO. "
      "Retorne exclusivamente JSON {\"entities\":[{\"id\":\"slug\",\"name\":\"nome literal\",\"label\":\"Label\"}],"
      "\"edges\":[{\"source\":\"id\",\"target\":\"id\",\"type\":\"REL\",\"evidence\":\"trecho literal exato do texto\"}]}. "
      "Não invente informações. " + schema)
    raw=chat(instruction,text)
    match=re.search(r'\{.*\}',raw,re.S)
    if not match: raise ValueError('LLM não retornou JSON')
    data=json.loads(match.group())
    entities=[];ids=set()
    for e in data.get('entities',[]):
        if not isinstance(e,dict) or e.get('label') not in DOMAIN['labels']:continue
        name=str(e.get('name','')).strip()
        if not name or name.casefold() not in text.casefold(): continue
        ident=canonical(name)
        if not ident or ident in ids: continue
        entities.append({'id':ident,'name':name,'label':e['label']});ids.add(ident)
    edges=[]
    # LLM output id can differ from canonicalized id; remap by returned names
    ref={str(e.get('id')):canonical(str(e.get('name',''))) for e in data.get('entities',[]) if isinstance(e,dict)}
    for e in data.get('edges',[]):
        if not isinstance(e,dict):continue
        s=ref.get(str(e.get('source')));t=ref.get(str(e.get('target')))
        evidence=str(e.get('evidence','')).strip()
        if s in ids and t in ids and e.get('type') in DOMAIN['relations'] and evidence and evidence.casefold() in text.casefold():
            edges.append({'source':s,'target':t,'type':e['type'],'evidence':evidence})
    return entities,edges

def ingest(store,path,version='1.0',with_llm=True,with_embeddings=True):
    source=Path(path)
    doc_id=canonical(source.stem+'-'+version)
    store.put_document({'id':doc_id,'title':source.name,'version':version,'origin':str(source.name)})
    counts={'chunks':0,'entities':0,'relations':0,'warnings':[]}
    for locator,page in load_document(source):
        for i,text in enumerate(chunks_of(page)):
            chunk_id=f'{doc_id}-{canonical(locator)}-{i}'
            vector=None
            if with_embeddings:
                try:vector=embed(text)
                except Exception as exc:counts['warnings'].append(f'Embedding indisponível: {exc}')
            store.put_chunk({'id':chunk_id,'doc_id':doc_id,'text':text,'locator':locator,'embedding':vector})
            counts['chunks']+=1
            if with_llm:
                try:
                    entities,edges=extract_graph(text)
                    for e in entities:
                        store.put_entity(e);store.link_mention(chunk_id,e['id']);counts['entities']+=1
                    for edge in edges:
                        # Store literal provenance, not merely a model assertion
                        edge['evidence_id']=chunk_id
                        edge['source_type']='llm_verified_excerpt'
                        store.put_edge(edge);counts['relations']+=1
                except Exception as exc:
                    counts['warnings'].append(f'NER/RE falhou em {chunk_id}: {exc}')
    return counts
