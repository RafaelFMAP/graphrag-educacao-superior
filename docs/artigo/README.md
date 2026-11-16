# Artigo técnico (formato SBC)

- `main.tex`: texto do artigo, em português, com resumo e abstract.
- `referencias.bib`: referências bibliográficas.
- `figuras/subgrafo.png`: captura do subgrafo de contexto gerada pela aplicação.

## Como compilar

**Overleaf (recomendado):** crie um projeto a partir do modelo *SBC Conferences Template* da galeria do Overleaf, que inclui `sbc-template.sty` e `sbc.bst`. Substitua o arquivo principal por `main.tex` e envie `referencias.bib` e a pasta `figuras/`.

**Local:** com uma distribuição LaTeX (TeX Live ou MiKTeX), coloque `sbc-template.sty` e `sbc.bst` nesta pasta e execute `latexmk -pdf main.tex`. Sem esses arquivos, o documento compila com uma formatação equivalente (A4, Times 12 pt) e bibliografia no estilo `plain`, útil para revisão.

Antes da entrega, preencha autores, instituição e e-mails e revise os números da seção de avaliação contra `docs/resultados/`.
