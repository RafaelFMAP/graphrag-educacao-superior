"""Ollama is optional for ingestion and answer generation; clear error on outage."""
import requests
from config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_EMBED_MODEL

def chat(system, prompt):
    resp=requests.post(f"{OLLAMA_URL}/api/chat",json={"model":OLLAMA_MODEL,"stream":False,"messages":[{"role":"system","content":system},{"role":"user","content":prompt}]},timeout=120)
    resp.raise_for_status()
    return resp.json()["message"]["content"]

def embed(text):
    response=requests.post(f"{OLLAMA_URL}/api/embed",json={"model":OLLAMA_EMBED_MODEL,"input":text},timeout=60)
    response.raise_for_status()
    embedding=response.json()["embeddings"][0]
    if len(embedding)!=768: raise ValueError("O índice espera embeddings de 768 dimensões (nomic-embed-text).")
    return embedding
