"""Verificação de citações e nível de confiança da resposta.

A confiança é uma heurística transparente, não uma probabilidade calibrada.
Ela combina quatro sinais em [0, 1]:

  fundamentacao  fração das citações da resposta que existem no contexto (peso 0,40)
  recuperacao    força do melhor trecho na busca vetorial                   (peso 0,25)
  grafo          entidades-âncora encontradas e caminhos recuperados       (peso 0,20)
  cypher         a consulta Text2Cypher devolveu linhas                    (peso 0,15)

Sinais indisponíveis (por exemplo, sem LLM) saem da média e os pesos são
renormalizados. Faixas: >= 0,70 Alta; >= 0,45 Média; abaixo disso, Baixa.
"""
import re

WEIGHTS = {'fundamentacao': 0.40, 'recuperacao': 0.25, 'grafo': 0.20, 'cypher': 0.15}
CITATION = re.compile(r'\b([TPCG]\d{1,3})\b')
ABSTENTION = re.compile(r'n[ãa]o h[áa] evid[êe]ncia|n[ãa]o (?:é|e) poss[íi]vel (?:responder|afirmar|decidir)|'
                        r'evid[êe]ncias? insuficientes?|n[ãa]o (?:consta|aparece|encontrei)', re.I)


def citations(answer):
    seen = []
    for c in CITATION.findall(answer or ''):
        if c not in seen: seen.append(c)
    return seen


def verify_citations(answer, valid_ids):
    cited = citations(answer)
    valid = [c for c in cited if c in valid_ids]
    return {'cited': cited, 'valid': valid, 'invalid': [c for c in cited if c not in valid_ids]}


def is_abstention(answer):
    return bool(ABSTENTION.search(answer or ''))


def clamp(x):
    return max(0.0, min(1.0, x))


def score(check=None, best_vector_score=None, anchors=0, paths=0, cypher_rows=None, abstained=False):
    """`check` vem de verify_citations (None sem LLM); `cypher_rows` é None se o Text2Cypher não rodou.

    Uma abstenção ("não há evidência suficiente") é sempre classificada como Baixa:
    a confiança mede o quanto a resposta afirma fatos sustentados, e ela não afirma nenhum.
    """
    signals = {}
    if check is not None:
        signals['fundamentacao'] = len(check['valid']) / len(check['cited']) if check['cited'] else 0.0
    if best_vector_score is not None:
        # score do Neo4j = (1 + cos) / 2; 0,80 já indica trecho fortemente relacionado
        signals['recuperacao'] = clamp((best_vector_score - 0.60) / 0.20)
    signals['grafo'] = 1.0 if anchors and paths else (0.5 if anchors or paths else 0.0)
    if cypher_rows is not None:
        signals['cypher'] = 1.0 if cypher_rows > 0 else 0.0
    total_weight = sum(WEIGHTS[k] for k in signals)
    value = sum(WEIGHTS[k] * v for k, v in signals.items()) / total_weight if total_weight else 0.0
    level = 'Alta' if value >= 0.70 else ('Média' if value >= 0.45 else 'Baixa')
    if abstained:
        level = 'Baixa'
    return {'score': round(value, 2), 'level': level, 'abstention': abstained,
            'signals': {k: round(v, 2) for k, v in signals.items()}}
