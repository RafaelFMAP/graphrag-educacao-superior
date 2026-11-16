"""Grounded hybrid RAG with paths; never execute user-generated Cypher."""
import re
from ollama_client import chat,embed
from config import DOMAIN

def retrieve(store,question):
    chunks={}
    try:
        vector=embed(question)
        for row in store.vector_chunks(vector):chunks[row['id']]=row
    except Exception:pass
    try:
        for row in store.fulltext_chunks(question):chunks.setdefault(row['id'],row)
    except Exception:pass
    try:paths=store.nearby(question)
    except Exception:paths=[]
    return {'chunks':list(chunks.values())[:10],'paths':paths}

def answer(store,question,use_llm=True):
    context=retrieve(store,question)
    chunks=context['chunks'];paths=context['paths']
    if not chunks and not paths:
        return {'answer':'Não há evidência recuperada para responder com segurança. Faça a ingestão de documentos ou reformule a busca.','context':context}
    excerpts='\n'.join(f"[TRECHO {x['id']}] {x['text'][:1200]}" for x in chunks)
    triples='\n'.join(f"[{e['source_name']}] -{e['relation']}-> [{e['target_name']}] (evidência: {e.get('evidence_id') or 'semente sintética'})" for e in paths)
    if not use_llm:
        return {'answer':'Evidências recuperadas (geração por LLM desativada). Consulte os trechos e os caminhos abaixo.','context':context}
    system=(f"Você é assistente especializado em {DOMAIN['domain']}. "
      "Responda exclusivamente com base nos TRECHOS e CAMINHOS fornecidos. "
      "Cite IDs de trechos e caminhos usados. Se faltarem evidências, diga explicitamente. "
      "Não invente normas, decisões nem fatos. " + DOMAIN['warning'])
    try:
        result=chat(system,f'Pergunta: {question}\n\nTRECHOS:\n{excerpts}\n\nCAMINHOS:\n{triples}')
    except Exception as exc:
        result=f'Ollama indisponível ({exc}). Evidências recuperadas abaixo; não foi gerada resposta.'
    return {'answer':result,'context':context}
