"""Ollama is optional for ingestion and answer generation; clear error on outage."""
import requests
from config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_EMBED_MODEL

EMBED_DIMENSIONS = 768


def chat(system, prompt, format=None, options=None, timeout=180):
    """Chat call. `format` accepts "json" or a JSON Schema (structured output)."""
    payload = {"model": OLLAMA_MODEL, "stream": False,
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
    if format is not None:
        payload["format"] = format
    if options:
        payload["options"] = options
    resp = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def embed_many(texts):
    if not texts:
        return []
    response = requests.post(f"{OLLAMA_URL}/api/embed", json={"model": OLLAMA_EMBED_MODEL, "input": list(texts)}, timeout=120)
    response.raise_for_status()
    embeddings = response.json()["embeddings"]
    if any(len(e) != EMBED_DIMENSIONS for e in embeddings):
        raise ValueError("O índice espera embeddings de 768 dimensões (nomic-embed-text).")
    return embeddings


def embed(text):
    return embed_many([text])[0]
