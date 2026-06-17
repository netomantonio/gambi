# Observabilidade — Wide Events (CAP-6)

Como **testar e usar** os logs do GAMBI para descobrir, em uma linha, se uma falha (ex.: o 502 do
agent/plan mode) nasceu **no GAMBI** ou **no StackSpot**.

> Contrato: [SPEC CAP-6](../_bmad-output/planning-artifacts/specs/spec-gambi/SPEC.md) +
> companion [observability-wide-events.md](../_bmad-output/planning-artifacts/specs/spec-gambi/observability-wide-events.md).
> Arquitetura: [architecture-cap6-observability.md](../_bmad-output/planning-artifacts/architecture-cap6-observability.md).

## O que mudou

Antes, o único sinal de uma falha era o HTTP status code (`502`), e o body do StackSpot era
descartado. Agora **toda request a `/v1/chat/completions` emite um evento estruturado** (uma linha)
ao encerrar, com tudo que decide o diagnóstico: modo, contagem de tools, agent resolvido, latências,
status do upstream e — sob flag — o body bruto que o StackSpot devolveu.

Barato por padrão: sem flags, só metadados (nenhum corpo, nenhum custo de copiar payload).

## Flags (variáveis de ambiente)

| Variável | Default | Efeito |
|---|---|---|
| `GAMBI_LOG_FORMAT` | `console` | `json` → uma linha JSON por request (pronto p/ agregador). `console` → `key=value` legível. |
| `GAMBI_LOG_BODIES` | *(off)* | `1`/`true` → inclui `upstream_request_body` e `upstream_error_body`, **truncados + redacted**. |
| `GAMBI_LOG_RAW` | *(off)* | `1`/`true` → inclui corpos **crus** (sem corte, **sem redaction**). Só p/ debug local. Implica bodies. |
| `GAMBI_LOG_MAX_BODY` | `2000` | Limite de chars no truncamento dos corpos (modo `bodies`). |
| `GAMBI_LOG_FILE` | *(off)* | Caminho de arquivo. O GAMBI escreve os wide events (crus) **e** os diagnósticos `gambi.*` nele (append), sem depender de pipe do shell. |
| `GAMBI_LOG_LEVEL` | `INFO` | Nível dos logs `gambi.*` (diagnóstico geral). O logger de eventos `gambi.events` é sempre `INFO`. |

**Privacidade (piso, vale até em `raw`):** o header `Authorization`/Bearer e o `client_secret`
**nunca** são logados. No modo `bodies`, segredos (token, api_key, client_secret, authorization) são
mascarados como `***`.

## Como rodar com observabilidade ligada

Adicione ao seu `.env` (já carregado via `--env-file .env`) e rode normalmente:

```dotenv
GAMBI_LOG_FORMAT=json
GAMBI_LOG_BODIES=1
GAMBI_LOG_MAX_BODY=8000
GAMBI_LOG_LEVEL=DEBUG
GAMBI_LOG_FILE=gambi-debug.log
```
```bash
uv run uvicorn gambi.main:app --env-file .env --reload
```

No VS Code, reproduza o caso que falha (agent/plan mode usando uma tool). Sai **uma linha por
request** — no terminal do uvicorn **e** no `gambi-debug.log` (graças ao `GAMBI_LOG_FILE`; não precisa
de `Tee`/`2>&1`, que no PowerShell 5.1 estragam as linhas de executável nativo). Depois ache a do
turno que falhou:

```powershell
Select-String -Path gambi-debug.log -Pattern 'upstream_error'
```

## Como ler — receita de diagnóstico

Olhe o par **`outcome` + `upstream_status`**:

| `outcome` | `upstream_status` | Leitura |
|---|---|---|
| `success` | 200 | OK |
| `upstream_error` | 4xx/5xx preenchido | **Culpa do StackSpot.** Ex.: `429`/`402`/`403` = quota/crédito ("Credit Limit Reached"); `400`/`413` = payload/token-limit. Veja `upstream_error_body`. |
| `upstream_error` | *(ausente/null)* | **Falha de transporte** (rede/TLS/timeout) entre GAMBI e StackSpot — não foi recusa do StackSpot. |
| `internal_error` / `schema_unmatched` | ausente ou 200 | **Culpa do GAMBI** (exceção interna, ou o agent respondeu 200 mas fora do schema). |
| `model_not_found` | — | `model` do request não está no catálogo (`GAMBI_AGENTS`/arquivo). |

Pistas extras para o 502 do agent mode:
- **`n_tool_results > 0`** → é um turno de *follow-up* (o cliente já executou uma tool e reenviou) — o suspeito nº1.
- **`prompt_chars`** alto + `upstream_status` 400/413 → o prompt com todos os schemas de tools estourou um limite.
- **`agent_action`** = `tool_call` | `final` | `unmatched`. `unmatched` (com `http_status` 200!) é a falha-irmã do 502: o agent não emitiu o JSON estruturado e o loop de tools do editor trava.

## Exemplos

**StackSpot recusou por crédito (culpa do StackSpot):**
```json
{"request_id":"4c4f…","method":"POST","path":"/v1/chat/completions","http_status":502,
 "duration_ms":812.4,"model":"stk-5.1","mode":"agent","n_tools":71,"n_tool_results":2,
 "agent_id":"01ABC","upstream_status":429,"outcome":"upstream_error",
 "upstream_error_body":"{\"message\":\"Credit Limit Reached\",\"token\":\"***\"}"}
```

**Sucesso em agent mode (tool call emitida):**
```
request_id=ab12… method=POST path=/v1/chat/completions http_status=200 duration_ms=640.1
model=stk-5.1 mode=agent n_tools=24 agent_id=01ABC agent_action=tool_call outcome=success
```

**Falha de rede (não foi o StackSpot):** `outcome=upstream_error` **sem** `upstream_status`.

## Catálogo de campos

Resumido aqui; a tabela completa (campo → camada de origem → nível de verbosidade) está no companion
[observability-wide-events.md](../_bmad-output/planning-artifacts/specs/spec-gambi/observability-wide-events.md).

`request_id`, `method`, `path`, `http_status`, `duration_ms`, `model`, `mode`, `stream`,
`n_messages`, `n_tools`, `n_tool_results`, `tool_names`, `agent_id`, `agent_action`, `schema_repairs`,
`prompt_chars`, `upstream_url`, `upstream_status`, `upstream_latency_ms`, `outcome`, `error_type`,
`error_detail` (classe+msg da exceção de transporte: distingue read-timeout de "servidor desconectou"),
e — só sob flag — `upstream_request_body`, `upstream_error_body`.

## "Agent/plan mode não usa stream? Por que não-streaming?"

Usa, **para o cliente**: o VS Code sempre manda `stream:true` e **continua recebendo SSE** do GAMBI.
O que é não-streaming é a chamada **ao StackSpot** (upstream), e só em **agent mode**:

- **ask mode** (sem tools): GAMBI faz streaming upstream → repassa deltas como SSE. Streaming ponta a ponta.
- **agent mode** (com tools, ou agent com `structured_output`): o agent responde um **JSON do nosso
  schema** (`{"action":"tool_call"|"final", ...}`). Esse JSON precisa ser lido **inteiro** para decidir
  se vira `tool_calls` ou conteúdo, e para parsear a lista de tool calls. Por isso o GAMBI **bufferiza
  o upstream** (não-stream), parseia, e **só então** emite SSE limpo ao editor. Se repassássemos o
  stream cru, vazaria fragmento de JSON (`"action"...`) no chat — há testes que proíbem isso.

Dá pra manter stream também no upstream do agent mode? Em tese sim, mas o ganho é pequeno: uma
`tool_call` só pode ser emitida depois do JSON completo de qualquer forma. O único caso que se
beneficiaria é a **resposta final em texto** (`action:"final"`), que poderia sair token a token.
Isso depende do formato do SSE do StackSpot (**OQ-1**, não documentado) e da emissão de evento em
falha parcial de stream (**OQ-7**) — ficou fora do v1. Bônus do buffer atual: o erro do agent mode
sai **limpo**, o que é exatamente o que deixa o wide event diagnosticar o 502.

## Testar (a suíte de CAP-6)

```bash
uv run pytest tests/unit/test_wide_event.py tests/unit/test_emit.py \
              tests/unit/test_redaction.py tests/unit/test_observability_config.py \
              tests/integration/test_wide_event_middleware.py \
              tests/e2e/test_wide_event_e2e.py -q
uv run pytest        # suíte inteira (95 testes)
```

O teste-âncora de CAP-6 é
`tests/e2e/test_wide_event_e2e.py::test_upstream_4xx_event_diagnoses_stackspot_not_gambi`: com client
real (httpx+respx), StackSpot devolve `429` → o evento sai com `upstream_status=429` e
`outcome="upstream_error"`.

## Pendências

- **Validar no corp env real:** reproduzir o 502 em agent mode com `GAMBI_LOG_BODIES=1` e ler o evento.
- **Streaming puro** (`stream:true` ask-mode falhando no meio): emissão de evento em falha parcial — OQ-7.
