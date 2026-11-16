# Qualidade da extração (Text-to-Graph) — 2026-11-16 04:36

Modelo: `llama3.2:3b` · 3 documentos · 1388 s.

| Conjunto | Precisão | Revocação | F1 | Acertos / extraídas / gabarito |
|---|---|---|---|---|
| Entidades (só canonicalização) | 0.84 | 0.63 | 0.72 | 61 / 73 / 97 |
| Entidades (com resolução) | 0.86 | 0.63 | 0.73 | 61 / 71 / 97 |
| Relações (evidência literal) | 0.53 | 0.12 | 0.20 | 20 / 38 / 167 |
| Relações (+ assinatura de tipos) | 0.80 | 0.12 | 0.21 | 20 / 25 / 167 |

**Decisões da resolução de entidades** (entidades extraídas cujo id canônico difere do id final):

- fuzzy: errada: 2
  - "7º período da Matriz 2026" (Campus) → `6o-periodo-da-matriz-2026` por fuzzy: errada
  - "8º período da Matriz 2026" (Campus) → `6o-periodo-da-matriz-2026` por fuzzy: errada

Trechos com falha de extração: 1.

> Depois desta execução, a proteção de numerais da resolução de entidades passou a reconhecer ordinais (`7º` ≠ `6º`), o que corrige as 2 fusões erradas acima (teste `test_ordinals_are_numerals`). A falha restante foi uma saída JSON truncada pelo limite de 1.500 tokens (`num_predict`) num trecho com muitas entidades; o limite evita que o modelo gere sem parar no modo JSON estruturado.
