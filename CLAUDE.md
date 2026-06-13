# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## O que é o GAMBI

Proxy que expõe uma **API OpenAI-compatible** e traduz as chamadas para **agents do StackSpot**. O cliente fala "OpenAI"; o GAMBI fala "StackSpot" por baixo.

Idioma dos artefatos e da comunicação: **Português** (definido em `_bmad/config.toml`).

## Stack

- Python 3.12, FastAPI, httpx (cliente async p/ StackSpot), pydantic v2
- Gerenciamento de dependências e ambiente com **uv**

## Comandos

> Greenfield: o projeto ainda não tem código nem `pyproject.toml`. Ao inicializar, use estes comandos (não invente outros gerenciadores).

```bash
uv sync                 # instala/atualiza o ambiente a partir do lock
uv add <pacote>         # adiciona dependência
uv run pytest           # roda toda a suíte
uv run pytest path/to/test_x.py::test_caso   # roda um único teste
uv run uvicorn gambi.main:app --reload        # sobe o proxy localmente
uv run ruff check .     # lint
uv run ruff format .    # formatação
```

Ajuste os caminhos (`gambi.main:app`, etc.) ao módulo real quando ele existir.

## Regras de trabalho (inegociáveis)

1. **Fluxo BMAD — spec antes de código.** Nenhuma feature começa pela implementação. A spec/PRD/arquitetura vem primeiro (skills `bmad-*`), e os artefatos vão para `_bmad-output/` (planning / implementation / test). Conhecimento de projeto fica em `docs/`.
2. **TDD.** Escreva o teste que falha antes do código que passa. Sem teste, não há feature.
3. **DDD / Arquitetura hexagonal.** O **domínio é a tradução OpenAI ↔ StackSpot** — é onde mora a lógica de negócio, livre de FastAPI e httpx. FastAPI (entrada HTTP OpenAI-compatible) e o cliente StackSpot (httpx) são **adapters** nas bordas; o domínio depende de portas (interfaces), nunca de frameworks.
4. **Não invente a API do StackSpot.** O que você não souber sobre contratos, endpoints, auth ou formato de payload do StackSpot **não deve ser chutado** — marque explicitamente como *pergunta aberta* (no código com `# PERGUNTA ABERTA:` e/ou no artefato BMAD correspondente) e siga sem fabricar comportamento.

## Referência do StackSpot

Antes de codar qualquer adapter do StackSpot, leia **`docs/stackspot/`** — documentação destilada da doc oficial, com o que está confirmado e o que é `PERGUNTA ABERTA`. Comece por:

- `docs/stackspot/README.md` — índice + perguntas abertas consolidadas.
- `docs/stackspot/07-mapeamento-openai-stackspot.md` — a tabela de tradução OpenAI↔StackSpot (= o domínio do GAMBI).
- `docs/stackspot/02-agents-api.md` — o endpoint central (`POST genai-inference-app.stackspot.com/v1/agent/{agentId}/chat`).

Fatos âncora: auth via OAuth `client_credentials` em `idm.stackspot.com/{realm}/oidc/oauth/token`; o agent **não** recebe `model`/`temperature` por request (são fixos na config do agent) — o `model` da OpenAI mapeia para o **`agentId`**. O **formato exato do SSE de streaming não está documentado** e é o maior bloqueio: trate como spike contra a API real antes de implementar `stream: true`.

## Onde as coisas vivem

- `docs/stackspot/` — referência destilada da API do StackSpot (ver acima).
- `_bmad-output/` — artefatos do fluxo BMAD (specs, stories, planos de teste). Gerados pelas skills, não edite à mão sem motivo.
- `docs/` — conhecimento de projeto / referência.
- `_bmad/` — instalação do BMAD (gerenciada pelo instalador, tratar como read-only; customizações em `_bmad/custom/`).
