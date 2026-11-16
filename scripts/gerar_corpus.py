"""Gera o corpus sintético (data/corpus/*.md) e o grafo-gabarito (data/seed.json).

Uma única definição estruturada produz os textos e as relações. Assim, cada
aresta do gabarito aponta para uma frase que existe literalmente no corpus.
Execute novamente depois de alterar os dados abaixo:

    python scripts/gerar_corpus.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline import canonical  # noqa: E402

COMPETENCIAS = {
    "Pensamento Computacional": "decompor problemas, abstrair e formular algoritmos corretos e eficientes.",
    "Raciocínio Lógico-Matemático": "aplicar lógica, matemática discreta, cálculo e estatística à computação.",
    "Desenvolvimento de Software": "projetar, implementar, testar e manter sistemas de software de qualidade.",
    "Modelagem de Dados": "modelar, armazenar e consultar dados em bancos relacionais, NoSQL e de grafos.",
    "Infraestrutura Computacional": "compreender e operar arquitetura, sistemas operacionais, redes e nuvem.",
    "Inteligência Artificial Aplicada": "construir e avaliar soluções de IA, aprendizado de máquina e linguagem natural.",
    "Comunicação Técnica": "comunicar resultados técnicos por escrito e oralmente, com ética e trabalho em equipe.",
    "Pesquisa e Inovação": "conduzir investigação científica e propor soluções inovadoras.",
}

# nome, período, carga horária, pré-requisitos, competências, ementa
DISCIPLINAS_2026 = [
    ("Algoritmos", 1, 80, [], ["Pensamento Computacional"], "lógica de programação, variáveis, estruturas condicionais e de repetição, funções e vetores."),
    ("Matemática Discreta", 1, 60, [], ["Raciocínio Lógico-Matemático"], "lógica proposicional, conjuntos, relações, indução matemática e combinatória."),
    ("Cálculo I", 1, 80, [], ["Raciocínio Lógico-Matemático"], "limites, derivadas e aplicações de derivadas."),
    ("Introdução à Ciência da Computação", 1, 40, [], ["Pensamento Computacional"], "história da computação, representação de dados e visão geral da área."),
    ("Comunicação e Expressão", 1, 40, [], ["Comunicação Técnica"], "leitura, produção de textos técnicos e apresentação oral."),
    ("Estruturas de Dados", 2, 80, ["Algoritmos"], ["Pensamento Computacional"], "listas, pilhas, filas, árvores, tabelas hash e análise básica de complexidade."),
    ("Programação Orientada a Objetos", 2, 80, ["Algoritmos"], ["Desenvolvimento de Software"], "classes, objetos, herança, polimorfismo e tratamento de exceções."),
    ("Cálculo II", 2, 80, ["Cálculo I"], ["Raciocínio Lógico-Matemático"], "integrais, séries e funções de várias variáveis."),
    ("Álgebra Linear", 2, 60, [], ["Raciocínio Lógico-Matemático"], "matrizes, sistemas lineares, espaços vetoriais e transformações lineares."),
    ("Arquitetura de Computadores", 2, 60, ["Introdução à Ciência da Computação"], ["Infraestrutura Computacional"], "organização de processadores, memória, entrada e saída e linguagem de montagem."),
    ("Banco de Dados", 3, 80, ["Estruturas de Dados"], ["Modelagem de Dados"], "modelo entidade-relacionamento, modelo relacional, SQL, normalização e transações."),
    ("Estruturas de Dados Avançadas", 3, 60, ["Estruturas de Dados"], ["Pensamento Computacional"], "árvores balanceadas, heaps, grafos e algoritmos de busca em grafos."),
    ("Probabilidade e Estatística", 3, 60, ["Cálculo II"], ["Raciocínio Lógico-Matemático"], "probabilidade, variáveis aleatórias, distribuições, inferência e regressão."),
    ("Sistemas Operacionais", 3, 60, ["Arquitetura de Computadores"], ["Infraestrutura Computacional"], "processos, threads, escalonamento, memória virtual e sistemas de arquivos."),
    ("Engenharia de Software", 3, 60, ["Programação Orientada a Objetos"], ["Desenvolvimento de Software"], "processos de software, requisitos, modelagem UML, testes e qualidade."),
    ("Projeto e Análise de Algoritmos", 4, 60, ["Estruturas de Dados Avançadas", "Matemática Discreta"], ["Pensamento Computacional"], "análise assintótica, divisão e conquista, programação dinâmica, algoritmos gulosos e NP-completude."),
    ("Redes de Computadores", 4, 60, ["Sistemas Operacionais"], ["Infraestrutura Computacional"], "modelo em camadas, TCP/IP, roteamento e protocolos de aplicação."),
    ("Teoria da Computação", 4, 60, ["Matemática Discreta"], ["Raciocínio Lógico-Matemático"], "linguagens formais, autômatos, máquinas de Turing e computabilidade."),
    ("Desenvolvimento Web", 4, 60, ["Banco de Dados", "Programação Orientada a Objetos"], ["Desenvolvimento de Software"], "HTTP, aplicações cliente-servidor, APIs REST e persistência."),
    ("Projeto Integrador", 4, 80, ["Estruturas de Dados", "Banco de Dados"], ["Desenvolvimento de Software", "Comunicação Técnica"], "desenvolvimento em equipe de um sistema completo, integrando conteúdos dos períodos anteriores."),
    ("Compiladores", 5, 60, ["Teoria da Computação"], ["Desenvolvimento de Software"], "análise léxica, sintática e semântica, geração e otimização de código."),
    ("Inteligência Artificial", 5, 60, ["Projeto e Análise de Algoritmos", "Probabilidade e Estatística"], ["Inteligência Artificial Aplicada"], "busca heurística, representação de conhecimento, raciocínio probabilístico e agentes."),
    ("Computação Gráfica", 5, 60, ["Álgebra Linear", "Estruturas de Dados"], ["Desenvolvimento de Software"], "transformações geométricas, rasterização, iluminação e pipeline gráfico."),
    ("Sistemas Distribuídos", 5, 60, ["Redes de Computadores"], ["Infraestrutura Computacional"], "comunicação entre processos, consistência, replicação e tolerância a falhas."),
    ("Interação Humano-Computador", 5, 40, ["Engenharia de Software"], ["Desenvolvimento de Software"], "usabilidade, acessibilidade, prototipação e avaliação de interfaces."),
    ("Aprendizado de Máquina", 6, 60, ["Inteligência Artificial", "Álgebra Linear"], ["Inteligência Artificial Aplicada"], "aprendizado supervisionado e não supervisionado, redes neurais e avaliação de modelos."),
    ("Segurança da Informação", 6, 60, ["Redes de Computadores"], ["Infraestrutura Computacional"], "criptografia, autenticação, vulnerabilidades e gestão de riscos."),
    ("Computação em Nuvem", 6, 40, ["Sistemas Distribuídos"], ["Infraestrutura Computacional"], "virtualização, contêineres, orquestração e modelos de serviço em nuvem."),
    ("Banco de Dados Avançado", 6, 60, ["Banco de Dados"], ["Modelagem de Dados"], "bancos NoSQL, bancos de dados orientados a grafos, indexação e processamento de consultas."),
    ("Ética e Computação", 6, 40, [], ["Comunicação Técnica"], "ética profissional, privacidade, LGPD e impactos sociais da computação."),
    ("Processamento de Linguagem Natural", 7, 60, ["Aprendizado de Máquina"], ["Inteligência Artificial Aplicada"], "representação de texto, embeddings, modelos de linguagem e recuperação de informação."),
    ("Grafos de Conhecimento", 7, 60, ["Banco de Dados Avançado", "Inteligência Artificial"], ["Modelagem de Dados", "Inteligência Artificial Aplicada"], "ontologias, modelo de grafo de propriedades, consultas em grafos e GraphRAG."),
    ("Tendências em Ciência da Computação", 7, 40, ["Aprendizado de Máquina"], ["Pesquisa e Inovação"], "temas emergentes da computação, como GraphRAG e KAG, por meio de projetos aplicados."),
    ("Trabalho de Conclusão de Curso I", 7, 40, ["Projeto Integrador", "Engenharia de Software"], ["Pesquisa e Inovação"], "definição do problema, revisão bibliográfica e projeto de pesquisa."),
    ("Empreendedorismo", 7, 40, [], ["Comunicação Técnica"], "modelos de negócio, inovação e startups de tecnologia."),
    ("Trabalho de Conclusão de Curso II", 8, 40, ["Trabalho de Conclusão de Curso I"], ["Pesquisa e Inovação"], "desenvolvimento, escrita e defesa do trabalho de conclusão."),
    ("Estágio Supervisionado", 8, 160, ["Projeto Integrador"], ["Desenvolvimento de Software"], "atuação profissional supervisionada em organização conveniada."),
    ("Tópicos Avançados em Computação", 8, 40, ["Projeto e Análise de Algoritmos"], ["Pesquisa e Inovação"], "conteúdo variável sobre temas avançados de algoritmos e computação."),
    ("Visão Computacional", 8, 60, ["Aprendizado de Máquina", "Computação Gráfica"], ["Inteligência Artificial Aplicada"], "processamento de imagens, extração de características e redes convolucionais."),
    ("Gestão de Projetos", 8, 40, ["Engenharia de Software"], ["Comunicação Técnica"], "planejamento, estimativas, métodos ágeis e gestão de riscos em projetos de software."),
]

# nome, período, carga horária, pré-requisitos (Matriz 2022)
DISCIPLINAS_2022 = [
    ("Introdução à Programação", 1, 80, []),
    ("Estruturas de Dados I", 2, 80, ["Introdução à Programação"]),
    ("Programação II", 2, 80, ["Introdução à Programação"]),
    ("Estruturas de Dados II", 3, 60, ["Estruturas de Dados I"]),
    ("Banco de Dados I", 3, 80, ["Estruturas de Dados I"]),
    ("Linguagens Formais", 4, 60, []),
    ("Laboratório de Projetos", 4, 80, ["Banco de Dados I", "Programação II"]),
    ("Sistemas Inteligentes", 5, 60, ["Estruturas de Dados II"]),
]

# disciplina da Matriz 2026 -> disciplina equivalente da Matriz 2022
EQUIVALENCIAS = [
    ("Algoritmos", "Introdução à Programação"),
    ("Estruturas de Dados", "Estruturas de Dados I"),
    ("Estruturas de Dados Avançadas", "Estruturas de Dados II"),
    ("Programação Orientada a Objetos", "Programação II"),
    ("Banco de Dados", "Banco de Dados I"),
    ("Teoria da Computação", "Linguagens Formais"),
    ("Inteligência Artificial", "Sistemas Inteligentes"),
    ("Projeto Integrador", "Laboratório de Projetos"),
]

ALIASES = {
    "Estruturas de Dados": ["ED"],
    "Programação Orientada a Objetos": ["POO"],
    "Banco de Dados": ["BD"],
    "Projeto e Análise de Algoritmos": ["PAA"],
    "Inteligência Artificial": ["IA"],
    "Aprendizado de Máquina": ["Machine Learning"],
    "Processamento de Linguagem Natural": ["PLN"],
    "Interação Humano-Computador": ["IHC"],
    "Trabalho de Conclusão de Curso I": ["TCC I"],
    "Trabalho de Conclusão de Curso II": ["TCC II"],
    "Regulamento Acadêmico 2026": ["Regulamento Acadêmico"],
    "Ciência da Computação": ["Bacharelado em Ciência da Computação"],
}

ATIVIDADES = ["Monitoria", "Iniciação Científica", "Maratona de Programação", "Extensão Universitária"]


def lista(nomes):
    return nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " e " + nomes[-1]


class Gabarito:
    def __init__(self):
        self.entities = {}
        self.edges = []

    def ent(self, name, label):
        ident = canonical(name)
        if ident in self.entities:
            assert self.entities[ident]["label"] == label, (name, label)
        else:
            self.entities[ident] = {"id": ident, "name": name, "label": label, "aliases": ALIASES.get(name, [])}
        return ident

    def rel(self, source, relation, target, evidence, document):
        self.edges.append({"source": canonical(source), "type": relation, "target": canonical(target),
                           "evidence": evidence, "document": document})


def ppc_2026(g):
    doc = "ppc-2026"
    out = ["# Projeto Pedagógico do Curso de Ciência da Computação (PPC 2026)", "",
           "> Documento sintético, criado para demonstração acadêmica. Não descreve uma instituição real.", ""]
    g.ent("PPC 2026", "Documento"); g.ent("Universidade Exemplo", "Instituicao"); g.ent("Campus Central", "Campus")
    g.ent("Ciência da Computação", "Curso"); g.ent("Matriz 2026", "MatrizCurricular"); g.ent("Matriz 2022", "MatrizCurricular")
    s1 = "A Universidade Exemplo possui o Campus Central, localizado na região metropolitana."
    s2 = "A Universidade Exemplo oferece o curso de Ciência da Computação no Campus Central, em regime presencial."
    s3 = "O PPC 2026 define a Matriz 2026, adotada pelo curso de Ciência da Computação a partir do primeiro semestre de 2026."
    s4 = "A Matriz 2026 substitui a Matriz 2022, que permanece válida apenas para estudantes ingressantes até 2025."
    out += ["## Apresentação", "", s1, "", s2, "", s3, "", s4, "",
            "O curso tem duração mínima de oito períodos e carga horária total de 3.200 horas, "
            "incluindo 200 horas de atividades complementares e 160 horas de estágio supervisionado.", ""]
    g.rel("Universidade Exemplo", "POSSUI", "Campus Central", s1, doc)
    g.rel("Universidade Exemplo", "OFERECE", "Ciência da Computação", s2, doc)
    g.rel("Campus Central", "OFERECE", "Ciência da Computação", s2, doc)
    g.rel("PPC 2026", "DEFINE", "Matriz 2026", s3, doc)
    g.rel("Ciência da Computação", "ADOTA", "Matriz 2026", s3, doc)
    g.rel("Matriz 2026", "SUBSTITUI", "Matriz 2022", s4, doc)

    out += ["## Matriz 2026 por período", ""]
    for periodo in range(1, 9):
        nomes = [d[0] for d in DISCIPLINAS_2026 if d[1] == periodo]
        frase = f"{periodo}º período da Matriz 2026 inclui: " + "; ".join(nomes) + "."
        out += [frase, ""]
        for nome in nomes:
            g.ent(nome, "Disciplina")
            g.rel("Matriz 2026", "INCLUI", nome, frase, doc)

    out += ["## Disciplinas, pré-requisitos e competências", ""]
    for nome, periodo, horas, pre, comps, ementa in DISCIPLINAS_2026:
        cabecalho = f"{nome} ({periodo}º período, {horas} h)"
        if not pre:
            f_pre = f"{cabecalho} não exige pré-requisitos."
        elif len(pre) == 1:
            f_pre = f"{cabecalho} exige {pre[0]} como pré-requisito."
        else:
            f_pre = f"{cabecalho} exige {lista(pre)} como pré-requisitos."
        f_comp = ("Desenvolve a competência " if len(comps) == 1 else "Desenvolve as competências ") + lista(comps) + "."
        out += [f"{f_pre} {f_comp} Ementa: {ementa}", ""]
        for p in pre:
            g.rel(nome, "EXIGE", p, f_pre, doc)
        for c in comps:
            g.ent(c, "Competencia")
            g.rel(nome, "DESENVOLVE", c, f"{f_pre} {f_comp}", doc)

    out += ["## Competências do egresso", ""]
    for nome, descricao in COMPETENCIAS.items():
        out += [f"Competência {nome}: {descricao}", ""]

    out += ["## Atividades complementares e estágio", "",
            "O curso de Ciência da Computação exige 200 horas de atividades complementares, "
            "conforme o Art. 25 do Regulamento Acadêmico 2026.", "",
            "O Estágio Supervisionado exige convênio entre a Universidade Exemplo e a organização concedente.", ""]
    return out


def ppc_2022(g):
    doc = "ppc-2022"
    out = ["# PPC 2022 — Matriz 2022 do curso de Ciência da Computação (em extinção)", "",
           "> Documento sintético, criado para demonstração acadêmica. Não descreve uma instituição real.", ""]
    g.ent("PPC 2022", "Documento")
    s1 = "O PPC 2022 define a Matriz 2022 do curso de Ciência da Computação."
    out += [s1, "", "A Matriz 2022 foi substituída pela Matriz 2026 e atende apenas estudantes ingressantes até 2025.", ""]
    g.rel("PPC 2022", "DEFINE", "Matriz 2022", s1, doc)
    nomes = [d[0] for d in DISCIPLINAS_2022] + ["Cálculo I"]
    s2 = "A Matriz 2022 inclui: " + "; ".join(nomes) + "."
    out += ["## Disciplinas da Matriz 2022", "", s2, ""]
    for nome in nomes:
        g.ent(nome, "Disciplina")
        g.rel("Matriz 2022", "INCLUI", nome, s2, doc)
    for nome, periodo, horas, pre in DISCIPLINAS_2022:
        cabecalho = f"{nome} ({periodo}º período da Matriz 2022, {horas} h)"
        if not pre:
            frase = f"{cabecalho} não exige pré-requisitos."
        else:
            frase = f"{cabecalho} exige {lista(pre)} como " + ("pré-requisito." if len(pre) == 1 else "pré-requisitos.")
        out += [frase, ""]
        for p in pre:
            g.rel(nome, "EXIGE", p, frase, doc)
    out += ["## Tabela de equivalências com a Matriz 2026", "",
            "Para a migração de estudantes, valem as equivalências abaixo, nos termos do Art. 21 do Regulamento Acadêmico 2026.", ""]
    for nova, antiga in EQUIVALENCIAS:
        frase = f"{nova} (Matriz 2026) equivale a {antiga} (Matriz 2022)."
        out += [frase, ""]
        g.rel(nova, "EQUIVALE_A", antiga, frase, doc)
    out += ["Disciplinas sem equivalência listada devem ser analisadas pela coordenação do curso.", ""]
    return out


def regulamento(g):
    doc = "regulamento-academico-2026"
    out = ["# Regulamento Acadêmico 2026 — Universidade Exemplo", "",
           "> Documento sintético, criado para demonstração acadêmica. Não descreve uma instituição real.", ""]
    g.ent("Regulamento 2026", "Documento"); g.ent("Regulamento Acadêmico 2026", "Regulamento")
    s1 = "O Regulamento 2026 define o Regulamento Acadêmico 2026 da Universidade Exemplo, aplicável a todos os cursos de graduação."
    artigos = {
        "Art. 12": "Pré-requisitos. O estudante só pode se matricular em uma disciplina depois de ser aprovado em todos os pré-requisitos dela, conforme a matriz curricular adotada pelo seu curso.",
        "Art. 15": "Quebra de pré-requisito. Em caráter excepcional, a coordenação do curso pode autorizar a quebra de pré-requisito para estudantes formandos, mediante requerimento justificado. A decisão é individual e não gera precedente.",
        "Art. 18": "Aproveitamento de estudos. A dispensa de disciplina por aproveitamento de estudos exige histórico escolar oficial, ementa cursada e compatibilidade mínima de 75% de carga horária e de conteúdo, avaliada pela coordenação do curso.",
        "Art. 21": "Equivalência entre matrizes. Estudantes da Matriz 2022 que migrarem para a Matriz 2026 terão as disciplinas cursadas aproveitadas segundo a tabela de equivalências do PPC 2022.",
        "Art. 25": "Atividades complementares. São reconhecidas como atividades complementares a Monitoria, a Iniciação Científica, a Maratona de Programação e a Extensão Universitária, até o limite de 80 horas por modalidade.",
        "Art. 30": "Trabalho de conclusão. O Trabalho de Conclusão de Curso I e o Trabalho de Conclusão de Curso II são individuais e avaliados por banca de três docentes.",
    }
    s2 = "O Regulamento Acadêmico 2026 possui os artigos " + lista(list(artigos)) + ", transcritos a seguir."
    out += [s1, "", s2, ""]
    g.rel("Regulamento 2026", "DEFINE", "Regulamento Acadêmico 2026", s1, doc)
    for art, texto in artigos.items():
        g.ent(art, "Artigo")
        g.rel("Regulamento Acadêmico 2026", "POSSUI", art, s2, doc)
        out += [f"{art}. {texto}", ""]
    for atividade in ATIVIDADES:
        g.ent(atividade, "AtividadeComplementar")
        g.rel("Art. 25", "DEFINE", atividade, f"Art. 25. {artigos['Art. 25']}", doc)
    for tcc in ("Trabalho de Conclusão de Curso I", "Trabalho de Conclusão de Curso II"):
        g.rel("Art. 30", "DEFINE", tcc, f"Art. 30. {artigos['Art. 30']}", doc)
    out += ["## Disposições finais", "",
            "Situações individuais, como pedidos de dispensa ou de quebra de pré-requisito, dependem de análise da secretaria e da coordenação do curso.", "",
            "Este regulamento não contém dados pessoais nem históricos de estudantes.", ""]
    return out


def main():
    g = Gabarito()
    docs = [
        ("ppc-2026", "PPC 2026", "PPC de Ciência da Computação 2026", "2026", ppc_2026(g)),
        ("ppc-2022", "PPC 2022", "PPC de Ciência da Computação 2022", "2022", ppc_2022(g)),
        ("regulamento-academico-2026", "Regulamento 2026", "Regulamento Acadêmico 2026", "2026", regulamento(g)),
    ]
    corpus = ROOT / "data" / "corpus"
    corpus.mkdir(parents=True, exist_ok=True)
    documents = []
    for ident, entity_name, title, version, lines in docs:
        text = "\n".join(lines).rstrip() + "\n"
        (corpus / f"{ident}.md").write_text(text, encoding="utf-8")
        documents.append({"id": ident, "file": f"corpus/{ident}.md", "title": title,
                          "version": version, "entity": canonical(entity_name)})
        for edge in g.edges:
            if edge["document"] == ident:
                assert edge["evidence"] in text, edge
    for e in g.entities.values():
        text = "".join((corpus / f"{d['id']}.md").read_text(encoding="utf-8") for d in documents)
        assert e["name"] in text, e
    seed = {"_comment": "Grafo-gabarito sintético gerado por scripts/gerar_corpus.py. Não edite à mão.",
            "documents": documents, "entities": list(g.entities.values()), "edges": g.edges}
    (ROOT / "data" / "seed.json").write_text(json.dumps(seed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(documents)} documentos, {len(g.entities)} entidades, {len(g.edges)} relações.")


if __name__ == "__main__":
    main()
