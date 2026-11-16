"""Avaliação comparativa: GraphRAG híbrido x RAG somente vetorial (baseline).

Para cada pergunta de data/questions.json (gabarito derivado do grafo-gabarito)
e para cada modo, mede:

  contexto   cobertura_contexto  fração das entidades/fatos esperados presentes nas evidências
             fonte_recuperada    algum trecho recuperado pertence a um documento esperado
  resposta   cobertura_resposta  fração das entidades/fatos esperados citados na resposta
             precisao_entidades  entidades citadas que são esperadas / todas as citadas
                                 (desconsiderando as que já estão na pergunta)
             exata               cobertura 1 e nenhuma entidade não esperada
  alucinação nao_esperadas       entidades do domínio citadas sem pertencer à resposta
             abstencao_correta   perguntas sem resposta: o sistema declarou não ter evidência
  grounding  citacoes_validas    citações que existem no contexto / citações feitas
  custo      segundos            latência total (recuperação + Text2Cypher + geração)

Uso:
  python evaluate.py                       # os dois modos, com LLM (lento em CPU)
  python evaluate.py --no-llm              # só métricas de contexto (rápido)
  python evaluate.py --modes graphrag --limit 5
Saída: docs/resultados/avaliacao.json e docs/resultados/avaliacao.md
"""
import argparse
import json
import time
import unicodedata
from pathlib import Path
from graph_store import GraphStore
from pipeline import find_mentions
from retrieval import answer, format_context
import confidence

ROOT = Path(__file__).parent
OUT = ROOT / 'docs' / 'resultados'
MODES = {'graphrag': 'GraphRAG híbrido', 'vector_only': 'Somente vetorial'}


def norm(text):
    text = unicodedata.normalize('NFKD', (text or '').casefold())
    return ''.join(c for c in text if not unicodedata.combining(c))


def coverage(expected_names, facts, mentioned_names, text):
    items = [n in mentioned_names for n in expected_names] + [norm(f) in norm(text) for f in facts]
    return sum(items) / len(items) if items else None


def evaluate_item(store, item, mode, catalog, use_llm):
    t0 = time.time()
    result = answer(store, item['question'], use_llm=use_llm, mode=mode)
    seconds = time.time() - t0
    context_text, _, _ = format_context(result['context'], result.get('cypher'))
    by_id = {e['id']: e['name'] for e in catalog}
    expected = set(item['expected_entities'])
    in_question = {by_id[i] for i in find_mentions(item['question'], catalog)}
    ctx_names = {by_id[i] for i in find_mentions(context_text, catalog)}
    row = {'id': item['id'], 'mode': mode, 'hops': item['hops'], 'category': item['category'],
           'answerable': item['answerable'], 'segundos': round(seconds, 1),
           'cobertura_contexto': coverage(expected, item['expected_facts'], ctx_names, context_text),
           'fonte_recuperada': (any(c['id'].startswith(s) for c in result['context']['chunks'] for s in item['expected_sources'])
                                if item['expected_sources'] else None)}
    if not use_llm:
        return row
    text = result['answer']
    mentioned = {by_id[i] for i in find_mentions(text, catalog)} - in_question
    unexpected = sorted(mentioned - expected)
    check = result.get('citations') or {'cited': [], 'valid': []}
    row.update({
        'resposta': text,
        'cobertura_resposta': coverage(expected, item['expected_facts'], mentioned | (in_question & expected), text),
        'precisao_entidades': (len(mentioned & expected) / len(mentioned)) if mentioned else None,
        'nao_esperadas': unexpected,
        'abstencao': confidence.is_abstention(text),
        'citacoes': len(check['cited']), 'citacoes_validas': len(check['valid']),
        'confianca': result['confidence']['level'],
    })
    if item['answerable']:
        row['exata'] = row['cobertura_resposta'] == 1 and not unexpected
    else:
        row['abstencao_correta'] = row['abstencao']
    return row


def mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 3) if values else None


def summarize(rows, use_llm):
    groups = {'Todas com resposta': lambda r: r['answerable'], '1 salto': lambda r: r['answerable'] and r['hops'] == 1,
              '2 saltos': lambda r: r['answerable'] and r['hops'] == 2, '3+ saltos': lambda r: r['answerable'] and r['hops'] >= 3,
              'Sem resposta': lambda r: not r['answerable']}
    summary = {}
    for mode in MODES:
        mode_rows = [r for r in rows if r['mode'] == mode]
        if not mode_rows:
            continue
        summary[mode] = {}
        for name, keep in groups.items():
            g = [r for r in mode_rows if keep(r)]
            if not g:
                continue
            s = {'n': len(g), 'cobertura_contexto': mean(r['cobertura_contexto'] for r in g),
                 'fonte_recuperada': mean(None if r['fonte_recuperada'] is None else float(r['fonte_recuperada']) for r in g)}
            if use_llm:
                cited = sum(r['citacoes'] for r in g)
                s.update({'cobertura_resposta': mean(r.get('cobertura_resposta') for r in g),
                          'precisao_entidades': mean(r.get('precisao_entidades') for r in g),
                          'exatas': mean(float(r['exata']) for r in g if 'exata' in r),
                          'com_entidade_nao_esperada': mean(float(bool(r['nao_esperadas'])) for r in g),
                          'abstencao_correta': mean(float(r['abstencao_correta']) for r in g if 'abstencao_correta' in r),
                          'citacoes_validas': round(sum(r['citacoes_validas'] for r in g) / cited, 3) if cited else None,
                          'sem_citacao': mean(float(r['citacoes'] == 0) for r in g),
                          'segundos': mean(r['segundos'] for r in g)})
            summary[mode][name] = s
    return summary


def fmt(v):
    if v is None:
        return '—'
    if isinstance(v, float):
        return f'{v:.2f}'
    return str(v)


def markdown(summary, meta):
    cols = ['n', 'cobertura_contexto', 'fonte_recuperada', 'cobertura_resposta', 'precisao_entidades', 'exatas',
            'com_entidade_nao_esperada', 'abstencao_correta', 'citacoes_validas', 'sem_citacao', 'segundos']
    lines = [f"# Resultados da avaliação — {meta['data']}", '',
             f"Modelo de geração: `{meta['modelo']}` · embeddings: `{meta['embeddings']}` · {meta['perguntas']} perguntas "
             f"(gabarito derivado do grafo-gabarito por `scripts/gerar_perguntas.py`).", '']
    for group in ['Todas com resposta', '1 salto', '2 saltos', '3+ saltos', 'Sem resposta']:
        present = [m for m in summary if group in summary[m]]
        if not present:
            continue
        used = [c for c in cols if any(summary[m][group].get(c) is not None for m in present)]
        lines += [f'## {group}', '', '| Métrica | ' + ' | '.join(MODES[m] for m in present) + ' |',
                  '|---|' + '---|' * len(present)]
        for c in used:
            lines.append(f'| {c} | ' + ' | '.join(fmt(summary[m][group].get(c)) for m in present) + ' |')
        lines.append('')
    lines += ['Definições das métricas no cabeçalho de `evaluate.py`. As respostas completas estão em `avaliacao.json`.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--modes', nargs='+', default=list(MODES), choices=list(MODES))
    parser.add_argument('--no-llm', action='store_true', help='só métricas de recuperação/contexto')
    parser.add_argument('--limit', type=int, default=None)
    args = parser.parse_args()
    items = json.loads((ROOT / 'data' / 'questions.json').read_text(encoding='utf8'))
    items = [x for x in items if not x.get('needs_manual_review', True)][:args.limit]
    if not items:
        print('Nenhuma pergunta revisada em data/questions.json.')
        return
    use_llm = not args.no_llm
    store = GraphStore()
    rows = []
    try:
        catalog = store.entity_candidates()
        for item in items:
            for mode in args.modes:
                row = evaluate_item(store, item, mode, catalog, use_llm)
                rows.append(row)
                print(f"{item['id']} {mode:11s} contexto={fmt(row['cobertura_contexto'])} "
                      + (f"resposta={fmt(row.get('cobertura_resposta'))} não_esperadas={len(row.get('nao_esperadas', []))} "
                         f"abstenção={row.get('abstencao')} {row['segundos']}s" if use_llm else ''), flush=True)
    finally:
        store.close()
    from config import OLLAMA_MODEL, OLLAMA_EMBED_MODEL
    meta = {'data': time.strftime('%Y-%m-%d %H:%M'), 'modelo': OLLAMA_MODEL if use_llm else 'sem LLM',
            'embeddings': OLLAMA_EMBED_MODEL, 'perguntas': len(items), 'modos': args.modes}
    summary = summarize(rows, use_llm)
    OUT.mkdir(parents=True, exist_ok=True)
    suffix = '' if use_llm else '-contexto'
    (OUT / f'avaliacao{suffix}.json').write_text(json.dumps({'meta': meta, 'resumo': summary, 'linhas': rows},
                                                            ensure_ascii=False, indent=2), encoding='utf8')
    (OUT / f'avaliacao{suffix}.md').write_text(markdown(summary, meta), encoding='utf8')
    print(markdown(summary, meta))


if __name__ == '__main__':
    main()
