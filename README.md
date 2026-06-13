# GAMBI

Proxy que expõe uma **API OpenAI-compatible** e traduz as chamadas para **agents do StackSpot AI** — para usar os agents como "modelos" no VS Code Copilot Chat (no molde de um Ollama local), sem assinatura do GitHub Copilot.

Veja `_bmad-output/planning-artifacts/specs/spec-gambi/SPEC.md` para o contrato e `docs/stackspot/` para a referência da API do StackSpot.

## Requisitos
- Python 3.12+, [uv](https://docs.astral.sh/uv/)

## Setup
```bash
uv sync
```

## Rodar
```bash
# variáveis (ver gambi/config.py)
export GAMBI_STACKSPOT_REALM=stackspot
export GAMBI_STACKSPOT_CLIENT_ID=...
export GAMBI_STACKSPOT_CLIENT_SECRET=...
export GAMBI_AGENTS="stackspot-dev=<agentId>,stackspot-arch=<agentId>"

uv run uvicorn gambi.main:app --reload
```

## Testes e lint
```bash
uv run pytest                       # toda a suíte
uv run pytest tests/unit -q         # só unit
uv run pytest tests/e2e/test_app.py::test_chat_completion_happy_path  # um teste
uv run ruff check . && uv run ruff format --check .
```

## Endpoints (v1)
- `GET /v1/models` — agents do StackSpot como modelos OpenAI.
- `POST /v1/chat/completions` — chat não-streaming (CAP-2).
- `GET /health` — liveness.

## Estado
PoC. Streaming (`stream:true`) e a integração validada com o VS Code dependem de spikes — ver
`_bmad-output/planning-artifacts/epics-and-stories.md` (EPIC-1/5/6) e as PERGUNTAS ABERTAS no SPEC.
Regra do projeto: **não inventar a API do StackSpot** — lacunas são PERGUNTA ABERTA.
