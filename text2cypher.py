"""Text2Cypher: o LLM gera uma consulta Cypher de leitura, validada antes de executar.

Camadas de proteção:
  1. Validação estática: uma única instrução de leitura (MATCH/OPTIONAL MATCH/WITH/UNWIND ... RETURN),
     sem cláusulas de escrita, administração ou procedimentos (CALL), com rótulos e
     relações somente da allowlist do domínio e LIMIT obrigatório (no máximo MAX_LIMIT).
  2. Execução em transação de leitura (o Neo4j recusa qualquer escrita) com timeout.
  3. Uma nova tentativa, enviando ao LLM o erro da primeira; se falhar de novo, a
     consulta é descartada e a resposta usa apenas a busca híbrida.
"""
import re
from config import DOMAIN

MAX_LIMIT = 100
DEFAULT_LIMIT = 50
STRUCTURAL_LABELS = {'Entity', 'Chunk', 'Document'}
STRUCTURAL_RELATIONS = {'MENTIONS', 'FROM_DOCUMENT', 'REPRESENTA'}
FORBIDDEN = ['CREATE', 'MERGE', 'DELETE', 'DETACH', 'SET', 'REMOVE', 'DROP', 'LOAD', 'CALL', 'FOREACH',
             'USE', 'ALTER', 'GRANT', 'REVOKE', 'DENY', 'TERMINATE', 'SHOW', 'START', 'STOP', 'INSERT', 'FINISH']

SCHEMA_TEXT = f"""Grafo de propriedades (Neo4j). Todos os nós de domínio têm o rótulo :Entity e um rótulo específico.
Propriedades de :Entity: id (slug), name (nome oficial), aliases (lista), kind (rótulo), pagerank (float), community (int).
Rótulos específicos: {', '.join(DOMAIN['labels'])}.
Relações (sempre nesta direção):
  (:Instituicao)-[:POSSUI]->(:Campus)
  (:Instituicao|Campus)-[:OFERECE]->(:Curso)
  (:Curso)-[:ADOTA]->(:MatrizCurricular)
  (:MatrizCurricular)-[:SUBSTITUI]->(:MatrizCurricular)   (a mais nova substitui a mais antiga)
  (:MatrizCurricular)-[:INCLUI]->(:Disciplina)
  (:Disciplina)-[:EXIGE]->(:Disciplina)                    (a disciplina exige o seu pré-requisito)
  (:Disciplina)-[:EQUIVALE_A]->(:Disciplina)               (disciplina da Matriz 2026 equivale a uma da Matriz 2022)
  (:Disciplina)-[:DESENVOLVE]->(:Competencia)
  (:Documento)-[:DEFINE]->(:MatrizCurricular|Regulamento)
  (:Regulamento)-[:POSSUI]->(:Artigo)
  (:Artigo)-[:DEFINE]->(:AtividadeComplementar|Disciplina)
Propriedades das relações: evidence (frase literal da fonte), evidence_id (trecho de origem)."""

FEW_SHOTS = [
    ("Quais são os pré-requisitos de Projeto Integrador?",
     "MATCH (d:Disciplina {name: 'Projeto Integrador'})-[:EXIGE]->(p:Disciplina)\nRETURN p.name AS prerequisito LIMIT 50"),
    ("Quais disciplinas antecedem indiretamente Grafos de Conhecimento?",
     "MATCH caminho = (d:Disciplina {name: 'Grafos de Conhecimento'})-[:EXIGE*2..6]->(p:Disciplina)\n"
     "RETURN DISTINCT p.name AS disciplina, min(length(caminho)) AS distancia ORDER BY distancia LIMIT 50"),
    ("Quais disciplinas exigem Algoritmos?",
     "MATCH (d:Disciplina)-[:EXIGE]->(:Disciplina {name: 'Algoritmos'})\nRETURN d.name AS disciplina LIMIT 50"),
    ("A que disciplina da Matriz 2022 equivale Banco de Dados?",
     "MATCH (:Disciplina {name: 'Banco de Dados'})-[:EQUIVALE_A]->(antiga:Disciplina)\nRETURN antiga.name AS equivalente LIMIT 50"),
    ("Quais disciplinas desenvolvem a competência Modelagem de Dados?",
     "MATCH (d:Disciplina)-[:DESENVOLVE]->(:Competencia {name: 'Modelagem de Dados'})\nRETURN d.name AS disciplina LIMIT 50"),
]

SYSTEM = ("Você converte perguntas em UMA consulta Cypher de LEITURA para Neo4j 5. "
          "Use somente os rótulos, relações e propriedades do esquema, na direção indicada. "
          "Use os nomes exatos das ENTIDADES RECONHECIDAS. Nunca escreva no banco. "
          "Responda apenas com a consulta, sem explicações e sem crases.\n\n" + SCHEMA_TEXT)


class CypherValidationError(ValueError):
    pass


def _strip_strings(query):
    return re.sub(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"", "''", query)


def clean(raw):
    """Remove cercas Markdown e prefixos comuns devolvidos por modelos pequenos."""
    text = raw.strip()
    fence = re.search(r"```(?:cypher)?\s*(.*?)```", text, re.S | re.I)
    if fence:
        text = fence.group(1).strip()
    text = re.sub(r"^(cypher|consulta)\s*:\s*", "", text, flags=re.I)
    return text.strip().rstrip(';').strip()


def validate(query):
    """Devolve a consulta normalizada (com LIMIT) ou levanta CypherValidationError."""
    query = clean(query)
    if not query:
        raise CypherValidationError('consulta vazia')
    bare = _strip_strings(query)
    if ';' in bare:
        raise CypherValidationError('apenas uma instrução é permitida')
    if '//' in bare or '/*' in bare:
        raise CypherValidationError('comentários não são permitidos')
    upper = bare.upper()
    for word in FORBIDDEN:
        if re.search(rf'\b{word}\b', upper):
            raise CypherValidationError(f'cláusula não permitida: {word}')
    if not re.match(r'^\s*(OPTIONAL\s+MATCH|MATCH|WITH|UNWIND)\b', upper):
        raise CypherValidationError('a consulta deve começar com MATCH, OPTIONAL MATCH, WITH ou UNWIND')
    if not re.search(r'\bRETURN\b', upper):
        raise CypherValidationError('a consulta deve ter RETURN')
    allowed_labels = set(DOMAIN['labels']) | STRUCTURAL_LABELS
    for group in re.findall(r'\(\s*\w*\s*((?::\s*`?[\wÀ-ÿ]+`?\s*(?:\|\s*`?[\wÀ-ÿ]+`?\s*)*)+)', bare):
        for label in re.findall(r'[\wÀ-ÿ]+', group):
            if label not in allowed_labels:
                raise CypherValidationError(f'rótulo não permitido: {label}')
    allowed_relations = set(DOMAIN['relations']) | STRUCTURAL_RELATIONS
    for group in re.findall(r'\[\s*\w*\s*:\s*([^\]*{]+)', bare):
        for rel in re.findall(r'[A-Za-z_]+', group):
            if rel not in allowed_relations:
                raise CypherValidationError(f'relação não permitida: {rel}')
    limit = re.search(r'\bLIMIT\s+(\d+)\s*$', upper)
    if limit is None:
        if re.search(r'\bLIMIT\b', upper):
            raise CypherValidationError('LIMIT deve ser um número no fim da consulta')
        query = f'{query}\nLIMIT {DEFAULT_LIMIT}'
    elif int(limit.group(1)) > MAX_LIMIT:
        query = re.sub(r'(?i)\bLIMIT\s+\d+\s*$', f'LIMIT {MAX_LIMIT}', query)
    return query


def build_prompt(question, entities, previous=None, error=None):
    shots = '\n\n'.join(f'Pergunta: {q}\nCypher:\n{c}' for q, c in FEW_SHOTS)
    known = ', '.join(f"{e['name']} ({e['label']})" for e in entities) or 'nenhuma'
    prompt = f"Exemplos:\n\n{shots}\n\nENTIDADES RECONHECIDAS: {known}\n\nPergunta: {question}\nCypher:"
    if previous:
        prompt += f"\n\nA consulta anterior falhou.\nConsulta: {previous}\nErro: {error}\nCorrija e devolva somente a consulta."
    return prompt


def generate_and_run(store, question, entities, chat_fn, timeout=5.0, retries=1):
    """Retorna {'query', 'rows', 'attempts', 'error'}; nunca levanta exceção."""
    attempts = []; previous = error = None
    for _ in range(retries + 1):
        try:
            raw = chat_fn(SYSTEM, build_prompt(question, entities, previous, error))
        except Exception as exc:
            return {'query': None, 'rows': [], 'attempts': attempts, 'error': f'LLM indisponível: {exc}'}
        candidate = clean(raw)
        try:
            query = validate(candidate)
            rows = store.run_read(query, timeout=timeout)
            attempts.append({'query': query, 'error': None})
            return {'query': query, 'rows': rows, 'attempts': attempts, 'error': None}
        except Exception as exc:
            error = str(exc).split('\n')[0][:300]
            attempts.append({'query': candidate, 'error': error})
            previous = candidate
    return {'query': None, 'rows': [], 'attempts': attempts, 'error': error}
