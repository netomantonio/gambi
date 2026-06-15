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
export GAMBI_STACKSPOT_REALM=<slug-da-conta>   # do portal "Access Token"; NÃO é o literal "stackspot"
export GAMBI_STACKSPOT_CLIENT_ID=...
export GAMBI_STACKSPOT_CLIENT_SECRET=...
export GAMBI_AGENTS="stackspot-dev=<agentId>,stackspot-arch=<agentId>"

uv run uvicorn gambi.main:app --reload   # sobe em http://localhost:8000
```

O `model_id` à esquerda de cada `=` em `GAMBI_AGENTS` (ex.: `stackspot-dev`) é o nome que você vai escolher no VS Code; o `<agentId>` à direita é o id do agent (copiado da URL do agent no portal StackSpot).

### Config por-agent (opções do StackSpot)
O `GAMBI_AGENTS` é o atalho simples (só `modelo=agentId`). Para definir **opções por agent** — campos confirmados na API real — use um **arquivo JSON** apontado por `GAMBI_AGENTS_FILE` (tem prioridade sobre `GAMBI_AGENTS`). Veja [gambi.agents.example.json](gambi.agents.example.json):
```json
[
  { "model_id": "stackspot-dev", "agent_id": "01ABC...",
    "stackspot_knowledge": false, "deep_search_ks": false,
    "return_ks_in_response": false, "knowledge_source_ids": [],
    "agent_version_number": 1 }
]
```
```bash
export GAMBI_AGENTS_FILE=./gambi.agents.json
```
Só `model_id` e `agent_id` são obrigatórios; o resto herda defaults seguros (`stackspot_knowledge` cai no `GAMBI_STACKSPOT_KNOWLEDGE`). Esses campos são enviados no request ao StackSpot (os mesmos do curl que você captura no portal).

## Integrar ao VS Code Copilot Chat

Guia completo em **[docs/vscode-setup.md](docs/vscode-setup.md)**. Resumo:

1. No VS Code, paleta de comandos → **`Chat: Manage Language Models`**.
2. **Add Models** → **Custom Endpoint** (OpenAI Compatible).
3. Preencha:
   - **URL:** `http://localhost:8000/v1/chat/completions` (a URL completa onde o GAMBI está rodando — o editor faz POST literal nela).
   - **API type:** **Chat Completions**.
   - **Model id:** um dos `model_id` do seu `GAMBI_AGENTS` (ex.: `stackspot-dev`).
   - **API key:** **qualquer valor não-vazio** (ex.: `gambi`). ⚠️ **O GAMBI ignora essa chave** — ele autentica no StackSpot com o `GAMBI_STACKSPOT_CLIENT_ID/SECRET` do servidor. O VS Code só exige o campo preenchido; o valor não importa.
4. Selecione o modelo no Copilot Chat e converse.

> O VS Code **não** consulta `GET /v1/models` no provider Custom Endpoint — você declara o modelo na config (passo 3). O `/v1/models` do GAMBI existe para outros clientes OpenAI.
>
> ⚠️ **Sem autenticação no GAMBI ainda:** qualquer um que alcance a URL do GAMBI pode usá-lo (ele guarda as credenciais StackSpot). Para uso além do `localhost`, trate auth/rede como item de hardening (fora do v1 — ver SPEC).

## Testes e lint
```bash
uv run pytest                       # toda a suíte
uv run pytest tests/unit -q         # só unit
uv run pytest tests/e2e/test_app.py::test_chat_completion_happy_path  # um teste
uv run ruff check . && uv run ruff format --check .
```

## Endpoints (v1)
- `GET /v1/models` — agents do StackSpot como modelos OpenAI.
- `POST /v1/chat/completions` — chat OpenAI; suporta `stream:false` (CAP-2) e `stream:true` (CAP-3, SSE).
- `GET /health` — liveness.

## Estado
PoC funcional. Chat e streaming implementados; o consumo do SSE do StackSpot é **defensivo**
(o formato exato não é público — OQ-1). **Valide no ambiente corporativo** seguindo o checklist em
[docs/stackspot/08-gaps-pesquisa.md](docs/stackspot/08-gaps-pesquisa.md): se o chat não-streaming
funciona mas o streaming sai estranho, é sinal de que o formato real do SSE difere do assumido —
me avise com a saída de um `curl -N` que eu ajusto o parser em `gambi/adapters/stackspot/stream.py`.
Regra do projeto: **não inventar a API do StackSpot** — lacunas são PERGUNTA ABERTA.
