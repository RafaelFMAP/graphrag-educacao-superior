# Resultados dos testes — 15/11/2026 (America/Sao_Paulo)

Ambiente: Windows com WSL 2; Docker Desktop 4.99.0; Docker Engine 29.9.3;
Compose 5.7.0. Python local 3.14 e Python 3.12 nas imagens Linux.

Resultados de CADA projeto (construção civil e educação superior):

| Verificação | Resultado |
|---|---|
| Testes unitários no Windows | 11/11 passaram |
| Testes unitários no container Linux final | 11/11 passaram, sem avisos do pytest |
| docker compose config -q | Passou |
| docker compose build | Passou (app e seed) |
| Inicialização completa do Compose | Passou; Neo4j, Ollama e app saudáveis |
| Download automático dos modelos | Passou; llama3.2:3b e nomic-embed-text |
| Carga dos dados com embeddings | Passou; 10 entidades e 11 relações por domínio |
| Busca textual, caminhos e referência de evidência | Passou |
| Embedding (768 dimensões) e busca vetorial | Passou |
| Chamada real de geração ao Ollama | Passou |
| Interface Streamlit via AppTest | Passou; três abas e nenhum erro de aplicação |
| Endpoint HTTP /_stcore/health | 200, ok em ambas as aplicações |

Comandos principais executados em cada pasta:

```bash
python -m pytest -q
docker compose config -q
docker compose build
docker compose up -d --wait --wait-timeout 600
docker compose exec -T app python smoke.py --llm
docker compose --profile test run --build --rm --no-deps tests
```

Também passou a execução sem modelos: seed.py --no-embeddings e smoke.py.
O AppTest emite um aviso de ScriptRunContext ao iniciar fora de uma sessão
interativa; não houve erro da interface.

Correções e adições: Dockerfile com usuário sem privilégios e healthcheck;
Compose com banco, Ollama, download dos modelos, seed, aplicação e perfil de testes;
volumes persistentes, ordem de inicialização e portas locais configuráveis;
.dockerignore; teste de integração smoke.py; validação de parâmetros de chunks_of
para impedir loop infinito quando overlap >= size (cinco casos de regressão).
A permissão da pasta /app também foi ajustada para permitir o cache do pytest.

Limites: estes testes confirmam funcionamento técnico em dados sintéticos, não
qualidade acadêmica das respostas ou correção semântica da extração por LLM.
evaluate.py foi executado e informou que as 20 perguntas ainda exigem revisão
humana e fontes esperadas; não há métricas de qualidade calculadas.
Os modelos e imagens são baixados durante a execução e não estão nos ZIPs.
As dependências usam faixas de versões e Ollama usa latest; futuras instalações
podem resolver versões diferentes. Modelos executados em CPU.

Referência para a ordem de inicialização:
https://docs.docker.com/compose/how-tos/startup-order/
