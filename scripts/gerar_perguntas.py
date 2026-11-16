"""Gera data/questions.json a partir do grafo-gabarito (data/seed.json).

As respostas esperadas são calculadas no gabarito, não escritas à mão: cada
pergunta traz as entidades que a resposta deve citar (`expected_entities`), os
fatos textuais esperados (`expected_facts`), os documentos que contêm a
evidência (`expected_sources`), o número de saltos e se ela tem resposta no
corpus (`answerable`). Perguntas sem resposta testam a abstenção.

    python scripts/gerar_perguntas.py
"""
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
seed = json.loads((ROOT / 'data' / 'seed.json').read_text(encoding='utf-8'))
NAME = {e['id']: e['name'] for e in seed['entities']}
ID = {e['name']: e['id'] for e in seed['entities']}
OUT = defaultdict(set)
DOCS = defaultdict(set)
for edge in seed['edges']:
    OUT[(edge['source'], edge['type'])].add(edge['target'])
    DOCS[(edge['source'], edge['type'], edge['target'])].add(edge['document'])


def targets(name, rel):
    return {NAME[t] for t in OUT[(ID[name], rel)]}


def sources(name, rel):
    return {NAME[s] for (s, r), ts in OUT.items() if r == rel and ID[name] in ts}


def closure(name, rel):
    seen, frontier = set(), {ID[name]}
    while frontier:
        nxt = set()
        for n in frontier:
            for t in OUT[(n, rel)]:
                if t not in seen:
                    seen.add(t); nxt.add(t)
        frontier = nxt
    return {NAME[i] for i in seen}


def depth(name, rel):
    best = 0; frontier = {ID[name]}; d = 0
    while frontier:
        d += 1
        frontier = {t for n in frontier for t in OUT[(n, rel)]}
        if frontier: best = d
    return best


Q = []


def q(question, category, hops, entities=(), facts=(), sources=('ppc-2026',), answerable=True):
    Q.append({'id': f'q{len(Q) + 1:02d}', 'question': question, 'category': category, 'hops': hops,
              'answerable': answerable, 'expected_entities': sorted(entities), 'expected_facts': list(facts),
              'expected_sources': list(sources), 'needs_manual_review': False})


# 1 salto: pré-requisitos diretos
for d in ['Projeto Integrador', 'Desenvolvimento Web', 'Inteligência Artificial', 'Visão Computacional', 'Banco de Dados']:
    q(f'Quais são os pré-requisitos diretos de {d}?', 'pré-requisito direto', 1, targets(d, 'EXIGE'))
# 1 salto, direção inversa
for d in ['Algoritmos', 'Aprendizado de Máquina', 'Engenharia de Software']:
    q(f'Quais disciplinas exigem {d} como pré-requisito?', 'dependentes diretos', 1, sources(d, 'EXIGE'))
# multi-hop: fecho transitivo de pré-requisitos
for d in ['Projeto Integrador', 'Grafos de Conhecimento', 'Trabalho de Conclusão de Curso II',
          'Processamento de Linguagem Natural', 'Compiladores']:
    q(f'Quais são todos os pré-requisitos, diretos e indiretos, de {d}?', 'pré-requisitos em cadeia',
      depth(d, 'EXIGE'), closure(d, 'EXIGE'))
# equivalências (1 salto, outro documento)
for d in ['Banco de Dados', 'Inteligência Artificial', 'Teoria da Computação']:
    q(f'A qual disciplina da Matriz 2022 equivale {d}?', 'equivalência', 1, targets(d, 'EQUIVALE_A'), sources=['ppc-2022'])
# 2 saltos combinando relações
eq = next(iter(targets('Estruturas de Dados Avançadas', 'EQUIVALE_A')))
q('Na Matriz 2022, qual é o pré-requisito da disciplina equivalente a Estruturas de Dados Avançadas?',
  'equivalência + pré-requisito', 2, targets(eq, 'EXIGE'), sources=['ppc-2022'])
comps = set().union(*[targets(p, 'DESENVOLVE') for p in targets('Inteligência Artificial', 'EXIGE')])
q('Quais competências são desenvolvidas pelos pré-requisitos diretos de Inteligência Artificial?',
  'pré-requisito + competência', 2, comps)
# competências (1 salto)
q('Quais disciplinas desenvolvem a competência Modelagem de Dados?', 'competência', 1, sources('Modelagem de Dados', 'DESENVOLVE'))
q('Quais competências a disciplina Projeto Integrador desenvolve?', 'competência', 1, targets('Projeto Integrador', 'DESENVOLVE'))
# matriz, documentos e instituição
q('Qual matriz curricular o curso de Ciência da Computação adota?', 'matriz', 1, targets('Ciência da Computação', 'ADOTA'))
q('Qual documento define a matriz curricular adotada pelo curso de Ciência da Computação?', 'matriz + documento', 2,
  sources(next(iter(targets('Ciência da Computação', 'ADOTA'))), 'DEFINE'))
q('Qual matriz curricular a Matriz 2026 substitui?', 'matriz', 1, targets('Matriz 2026', 'SUBSTITUI'))
q('Qual instituição oferece o curso de Ciência da Computação e em qual campus?', 'instituição', 1,
  sources('Ciência da Computação', 'OFERECE'))
# regulamento
q('Quais atividades complementares são reconhecidas pelo Regulamento Acadêmico 2026?', 'regulamento', 2,
  targets('Art. 25', 'DEFINE'), sources=['regulamento-academico-2026'])
q('Qual artigo do regulamento trata da quebra de pré-requisito?', 'regulamento (texto)', 1, ['Art. 15'],
  sources=['regulamento-academico-2026'])
q('Qual compatibilidade mínima de carga horária e conteúdo é exigida para dispensa por aproveitamento de estudos?',
  'regulamento (texto)', 1, facts=['75%'], sources=['regulamento-academico-2026'])
q('Quantas horas de atividades complementares o curso de Ciência da Computação exige?', 'carga horária (texto)', 1, facts=['200'])
q('Em qual período da Matriz 2026 é oferecida a disciplina Compiladores?', 'período (texto)', 1, facts=['5º'])
# sem resposta no corpus: o sistema deve se abster
for text in ['Qual é a nota da estudante Maria em Banco de Dados?',
             'O estudante João pode ser dispensado de Banco de Dados? Decida o caso dele.',
             'Quem é o coordenador do curso de Ciência da Computação?',
             'Quais são os pré-requisitos de Computação Quântica?',
             'Qual é a ementa de Física Quântica?',
             'Quais disciplinas a Matriz 2030 inclui?']:
    q(text, 'sem resposta', 0, sources=[], answerable=False)

(ROOT / 'data' / 'questions.json').write_text(json.dumps(Q, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'{len(Q)} perguntas: {sum(x["answerable"] for x in Q)} com resposta, {sum(not x["answerable"] for x in Q)} sem resposta.')
