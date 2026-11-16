"""Entity Resolution / Canonicalization: evita nós duplicados para a mesma entidade.

Estratégia em cascata, sempre restrita ao mesmo rótulo de domínio:
  1. id      — mesmo identificador canônico (acentos, caixa e pontuação normalizados)
  2. alias   — nome igual a um alias já registrado
  3. sigla   — sigla única que corresponde às iniciais de uma entidade ("POO", "TCC I")
  4. fuzzy   — similaridade de caracteres (rapidfuzz) acima do limiar ("Estrutura de Dados")
  5. vetor   — similaridade de embedding no índice entity_vector acima do limiar
  6. rótulo divergente — o mesmo id ou alias já existe com outro rótulo; o rótulo
     já registrado prevalece (modelos pequenos às vezes erram o rótulo) e o nó
     nunca é reetiquetado
Se nada casar, a entidade é nova.

Duas proteções bloqueiam fusões erradas nas etapas 4 e 5: numerais diferentes
("Cálculo I" ≠ "Cálculo II") e nomes em que um é extensão do outro
("Banco de Dados" ≠ "Banco de Dados Avançado").
"""
from rapidfuzz import fuzz
from pipeline import canonical

STOPWORDS = {"de", "da", "do", "das", "dos", "e", "a", "o", "em", "ao", "para", "na", "no"}
NUMERALS = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}

FUZZY_THRESHOLD = 90
# O Neo4j devolve score = (1 + cos) / 2 para similaridade de cosseno; 0,96 equivale a cos ≈ 0,92.
# Calibrado com nomic-embed-text no gabarito: "Aprendizagem de Máquina" -> "Aprendizado de Máquina" = 0,971,
# mas "Estruturas de Dados I" -> "Estruturas de Dados" = 0,973 e "Banco de Dados Avançado" -> "Banco de Dados"
# = 0,961; por isso o limiar só é seguro junto com as proteções de numeral e de extensão.
VECTOR_THRESHOLD = 0.96
ROMAN = {str(i): r for i, r in enumerate(["", "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"]) if i}


def tokens(name):
    return [t for t in canonical(name).split("-") if t]


def numerals(toks):
    return {ROMAN.get(t, t) for t in toks if t in NUMERALS or t.isdigit()}


def compatible(a, b):
    """Falso quando os nomes diferem só por numeral ou quando um estende o outro."""
    ta, tb = tokens(a), tokens(b)
    if numerals(ta) != numerals(tb):
        return False
    sa = {t for t in ta if t not in STOPWORDS}
    sb = {t for t in tb if t not in STOPWORDS}
    return not (sa < sb or sb < sa)


def acronym_key(name):
    """('poo', set()) para 'Programação Orientada a Objetos'; ('tcc', {'i'}) para 'TCC I'."""
    toks = tokens(name)
    words = [t for t in toks if t not in STOPWORDS and t not in NUMERALS and not t.isdigit()]
    return "".join(w[0] for w in words), frozenset(numerals(toks))


def is_acronym(name):
    letters = "".join(ch for ch in name if ch.isalpha())
    return 2 <= len(letters) <= 6 and name.replace(" ", "").isupper()


class EntityResolver:
    def __init__(self, store, embed_fn=None, fuzzy_threshold=FUZZY_THRESHOLD, vector_threshold=VECTOR_THRESHOLD):
        self.store = store
        self.embed_fn = embed_fn
        self.fuzzy_threshold = fuzzy_threshold
        self.vector_threshold = vector_threshold
        self._cache = {}
        self._all = None

    def _candidates(self, label):
        if label not in self._cache:
            self._cache[label] = list(self.store.entity_candidates(label))
        return self._cache[label]

    def _global(self):
        if self._all is None:
            self._all = list(self.store.entity_candidates(None))
        return self._all

    def remember(self, entity_id, name, label, aliases=()):
        entry = {"id": entity_id, "name": name, "label": label, "aliases": list(aliases)}
        self._candidates(label).append(entry)
        if self._all is not None:
            self._all.append(entry)

    def resolve(self, name, label):
        """Retorna (id, método, embedding_ou_None). Método 'novo' indica entidade inédita."""
        ident = canonical(name)
        candidates = self._candidates(label)
        for c in candidates:
            if c["id"] == ident or canonical(c["name"]) == ident:
                return c["id"], "id", None
        for c in candidates:
            if any(canonical(a) == ident for a in c.get("aliases", [])):
                return c["id"], "alias", None
        if is_acronym(name):
            toks = tokens(name)
            key = ("".join(t for t in toks if t not in NUMERALS and not t.isdigit()), frozenset(numerals(toks)))
            hits = {c["id"] for c in candidates if acronym_key(c["name"]) == key}
            if len(hits) == 1:
                return hits.pop(), "sigla", None
        best, best_score = None, 0
        for c in candidates:
            score = fuzz.ratio(ident, canonical(c["name"]))
            if score >= self.fuzzy_threshold and score > best_score and compatible(name, c["name"]):
                best, best_score = c, score
        if best:
            return best["id"], "fuzzy", None
        vector = None
        if self.embed_fn is not None:
            try:
                vector = self.embed_fn(name)
                for hit in self.store.vector_entities(vector, 5):
                    if (hit["label"] == label and hit["score"] >= self.vector_threshold
                            and compatible(name, hit["name"])):
                        return hit["id"], "vetor", vector
            except Exception:
                vector = None
        for c in self._global():
            if c["id"] == ident or any(canonical(a) == ident for a in c.get("aliases", [])):
                return c["id"], "rótulo divergente", None
        return ident, "novo", vector
