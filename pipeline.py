"""Text -> chunks -> entities/relation extraction -> entity resolution -> Neo4j with provenance."""
import json
import re
import unicodedata
from pathlib import Path
from pypdf import PdfReader
from config import DOMAIN
from ollama_client import chat, embed


def canonical(text):
    text = unicodedata.normalize('NFKD', text.lower())
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '-', text).strip('-')[:90]


def document_id(stem, version):
    """'ppc-2026' + '2026' -> 'ppc-2026' (sem repetir a versão); 'ppc' + '1.0' -> 'ppc-1-0'."""
    stem, version = canonical(stem), canonical(version)
    if not version or stem.endswith(version):
        return stem
    return f'{stem}-{version}'


def load_document(path):
    path = Path(path)
    if path.suffix.lower() == '.pdf':
        reader = PdfReader(str(path))
        return [(f"página {i+1}", page.extract_text() or '') for i, page in enumerate(reader.pages)]
    if path.suffix.lower() in ('.txt', '.md'):
        return [('texto', path.read_text(encoding='utf8'))]
    raise ValueError('Somente PDF, TXT ou MD são aceitos.')


def _fixed_chunks(text, size, overlap):
    out = []; start = 0
    while start < len(text):
        stop = min(len(text), start + size)
        out.append(text[start:stop])
        if stop == len(text): break
        start = stop - overlap
    return out


def chunks_of(text, size=900, overlap=140):
    """Agrupa parágrafos inteiros em trechos de até `size` caracteres.

    Parágrafos maiores que `size` são divididos em janelas fixas com `overlap`.
    O último título Markdown é repetido no início do trecho seguinte, para que
    cada trecho mantenha o contexto da seção.
    """
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError('Use size > 0 e 0 <= overlap < size')
    if not text.strip(): return []
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    out = []; current = ''; heading = ''
    for p in paragraphs:
        is_heading = p.startswith('#')
        if len(p) > size:
            if current: out.append(current)
            out.extend(_fixed_chunks(p, size, overlap)); current = ''
            continue
        if current and len(current) + 2 + len(p) > size:
            out.append(current)
            current = heading if heading and not is_heading and len(heading) + 2 + len(p) <= size else ''
        current = f'{current}\n\n{p}' if current else p
        if is_heading:
            heading = p
    if current and current != heading:
        out.append(current)
    elif current and not out:
        out.append(current)
    return out


EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string"}, "name": {"type": "string"}, "label": {"type": "string", "enum": DOMAIN['labels']}},
            "required": ["id", "name", "label"]}},
        "edges": {"type": "array", "items": {"type": "object", "properties": {
            "source": {"type": "string"}, "target": {"type": "string"},
            "type": {"type": "string", "enum": DOMAIN['relations']}, "evidence": {"type": "string"}},
            "required": ["source", "target", "type", "evidence"]}},
    },
    "required": ["entities", "edges"],
}


LABEL_GLOSSARY = ("Disciplina = componente curricular (ex.: Algoritmos, Banco de Dados); Curso = curso de graduação; "
                  "MatrizCurricular = matriz/grade (ex.: Matriz 2026); Competencia = competência desenvolvida; "
                  "Documento = PPC ou documento normativo; Regulamento = regulamento acadêmico; Artigo = artigo (ex.: Art. 12).")
RELATION_GLOSSARY = ("EXIGE liga a disciplina ao seu pré-requisito; INCLUI liga a matriz às disciplinas; "
                     "EQUIVALE_A liga disciplinas equivalentes; DESENVOLVE liga a disciplina à competência; "
                     "DEFINE liga o documento ao que ele define; ADOTA liga o curso à matriz.")
EXTRACTION_EXAMPLE = json.dumps({
    "entities": [{"id": "compiladores", "name": "Compiladores", "label": "Disciplina"},
                 {"id": "teoria-da-computacao", "name": "Teoria da Computação", "label": "Disciplina"}],
    "edges": [{"source": "compiladores", "target": "teoria-da-computacao", "type": "EXIGE",
               "evidence": "Compiladores (5º período, 60 h) exige Teoria da Computação como pré-requisito."}]},
    ensure_ascii=False)
RESERVED_NAMES = {x.casefold() for x in DOMAIN['labels'] + DOMAIN['relations']}


def clean_name(name):
    """Remove qualificadores finais entre parênteses e pontuação solta: 'Banco de Dados (Matriz 2026)' -> 'Banco de Dados'."""
    name = str(name).strip(' .,;:"\'“”')
    while True:
        stripped = re.sub(r'\s*\([^()]*\)\s*$', '', name)
        if stripped == name or not stripped: break
        name = stripped
    return name.strip(' .,;:"\'“”')


def _parse_json(raw):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', raw, re.S)
        if not match: raise ValueError('LLM não retornou JSON')
        return json.loads(match.group())


def extract_graph(text):
    """NER/RE via LLM; strict whitelist and evidence-string validation.
    Output is rejected if relationships have no literal supporting substring.
    """
    instruction = ("Extraia entidades e relações somente se forem sustentadas pelo TEXTO. "
                   "Retorne exclusivamente JSON {\"entities\":[{\"id\":\"slug\",\"name\":\"nome literal\",\"label\":\"Rótulo\"}],"
                   "\"edges\":[{\"source\":\"id\",\"target\":\"id\",\"type\":\"RELACAO\",\"evidence\":\"trecho literal exato do texto\"}]}. "
                   "Não invente informações. Use o nome da entidade sem qualificadores entre parênteses.\n"
                   f"Rótulos: {', '.join(DOMAIN['labels'])}. {LABEL_GLOSSARY}\n"
                   f"Relações: {', '.join(DOMAIN['relations'])}. {RELATION_GLOSSARY}\n"
                   f"Exemplo: {EXTRACTION_EXAMPLE}")
    raw = chat(instruction, text, format=EXTRACTION_SCHEMA, options={"temperature": 0})
    data = _parse_json(raw)
    entities = []; ids = set()
    for e in data.get('entities', []):
        if not isinstance(e, dict) or e.get('label') not in DOMAIN['labels']: continue
        name = clean_name(e.get('name', ''))
        if len(name) < 2 or name.casefold() in RESERVED_NAMES or name.casefold() not in text.casefold(): continue
        ident = canonical(name)
        if not ident or ident in ids: continue
        entities.append({'id': ident, 'name': name, 'label': e['label']}); ids.add(ident)
    edges = []
    # LLM output id can differ from canonicalized id; remap by returned names
    ref = {str(e.get('id')): canonical(clean_name(e.get('name', ''))) for e in data.get('entities', []) if isinstance(e, dict)}
    for e in data.get('edges', []):
        if not isinstance(e, dict): continue
        s = ref.get(str(e.get('source'))); t = ref.get(str(e.get('target')))
        evidence = str(e.get('evidence', '')).strip()
        if s in ids and t in ids and s != t and e.get('type') in DOMAIN['relations'] and evidence and evidence.casefold() in text.casefold():
            edges.append({'source': s, 'target': t, 'type': e['type'], 'evidence': evidence})
    return entities, edges


def find_mentions(text, entities):
    """IDs das entidades citadas no texto, casando nomes e aliases do mais longo ao mais curto.

    Um trecho já casado é mascarado; assim "Banco de Dados Avançado" não conta
    também como menção a "Banco de Dados". Siglas curtas exigem caixa exata.
    """
    names = []
    for e in entities:
        for n in [e['name'], *e.get('aliases', [])]:
            if n: names.append((n, e['id']))
    names.sort(key=lambda x: len(x[0]), reverse=True)
    found = []; masked = text
    for name, ident in names:
        flags = 0 if len(name) <= 4 else re.IGNORECASE
        pattern = re.compile(r'(?<![\wÀ-ÿ])' + re.escape(name) + r'(?![\wÀ-ÿ])', flags)
        if pattern.search(masked):
            if ident not in found: found.append(ident)
            masked = pattern.sub(lambda m: '\0' * len(m.group()), masked)
    return found


def ingest(store, path, version='1.0', with_llm=True, with_embeddings=True, title=None, doc_id=None):
    from entity_resolution import EntityResolver
    source = Path(path)
    doc_id = doc_id or document_id(source.stem, version)
    store.put_document({'id': doc_id, 'title': title or source.name, 'version': version, 'origin': str(source.name)})
    counts = {'document': doc_id, 'chunks': 0, 'entities': 0, 'relations': 0, 'mentions': 0, 'resolved': [], 'rejected': [], 'warnings': []}
    known = list(store.entity_candidates())
    resolver = EntityResolver(store, embed_fn=embed if with_embeddings else None)
    for locator, page in load_document(source):
        for i, text in enumerate(chunks_of(page)):
            chunk_id = f'{doc_id}-{canonical(locator)}-{i}'
            vector = None
            if with_embeddings:
                try: vector = embed(text)
                except Exception as exc: counts['warnings'].append(f'Embedding indisponível: {exc}')
            store.put_chunk({'id': chunk_id, 'doc_id': doc_id, 'text': text, 'locator': f'{locator} · trecho {i+1}', 'embedding': vector})
            counts['chunks'] += 1
            if with_llm:
                try:
                    entities, edges = extract_graph(text)
                    mapping = {}
                    for e in entities:
                        rid, method, evec = resolver.resolve(e['name'], e['label'])
                        mapping[e['id']] = rid
                        if method == 'novo':
                            store.put_entity({**e, 'id': rid, 'embedding': evec})
                            resolver.remember(rid, e['name'], e['label'])
                            known.append({'id': rid, 'name': e['name'], 'aliases': []})
                            counts['entities'] += 1
                        else:
                            store.add_alias(rid, e['name'])
                        counts['resolved'].append({'nome': e['name'], 'rótulo': e['label'], 'id': rid, 'método': method})
                    for edge in edges:
                        # Store literal provenance, not merely a model assertion
                        written = store.put_edge({**edge, 'source': mapping[edge['source']], 'target': mapping[edge['target']],
                                                  'evidence_id': chunk_id, 'source_type': 'llm_verified_excerpt'})
                        if written:
                            counts['relations'] += 1
                        else:
                            counts['rejected'].append(f"{mapping[edge['source']]} -{edge['type']}-> {mapping[edge['target']]}")
                except Exception as exc:
                    counts['warnings'].append(f'NER/RE falhou em {chunk_id}: {exc}')
            for entity_id in find_mentions(text, known):
                store.link_mention(chunk_id, entity_id); counts['mentions'] += 1
    return counts
