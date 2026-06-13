# Fechamento de GAPs — pesquisa estruturada (2026-06-13)

Sem acesso ao StackSpot fora do ambiente corporativo, estes GAPs foram investigados por pesquisa (doc oficial, código de comunidade, código-fonte do VS Code). Cada achado é **graduado por evidência**. O que permanece desconhecido tem estratégia defensiva + checklist de validação no corp env.

Confiança: **Confirmado-oficial** · **Provável-comunidade** · **Inferido** · **Desconhecido**.

---

## OQ-2 — Contrato do VS Code Custom Endpoint · ✅ RESOLVIDO

Fonte forte: código-fonte de `microsoft/vscode-copilot-chat` (`customOAIProvider.ts`, `openAIEndpoint.ts`) + changelog oficial.

| Pergunta | Resposta | Confiança |
|---|---|---|
| Chama `GET /v1/models`? | **Não.** O provider "Custom Endpoint" (`vendor: customendpoint`) lê os modelos do `chatLanguageModels.json`; cada modelo traz `id`, `name` e **`url` completa**. O VS Code faz POST literal nessa `url`. | Confirmado-oficial (código) |
| Formato de streaming | **SSE OpenAI-padrão:** `data: {chat.completion.chunk}` com `choices[].delta.content`, término `data: [DONE]`. | Confirmado-oficial |
| Sempre `stream:true`? | Sim, na prática. Injeta `stream_options:{include_usage:true}`, remove `max_tokens`, pode remover `temperature`. | Confirmado-oficial (código) |
| Auth | `Authorization: Bearer <apiKey>` (a key vem da config; não é validada pelo destino). | Confirmado-oficial |
| Disponibilidade | **Estável** (v1.120–1.123, changelog jun/2026). Selo "Insiders" da doc está defasado. | Confirmado-oficial |

**Implicações p/ o GAMBI:**
1. `GET /v1/models` é **opcional** para o Copilot Chat — mas **mantido** (clientes legados/comunidade e outros clients OpenAI o usam; custo baixo).
2. O usuário cola a **URL completa** do endpoint de chat no `chatLanguageModels.json` (ver `docs/vscode-setup.md`).
3. **Streaming SSE OpenAI-padrão é obrigatório** → motiva implementar CAP-3 já.
4. Aceitar e ignorar graciosamente `stream_options`, ausência de `max_tokens`/`temperature`.

---

## OQ-1 — Formato do SSE da Agents API StackSpot · ⚠️ DESCONHECIDO (impl. defensiva)

Não há fonte pública: doc oficial só diz "respostas em tempo real"; sem OpenAPI público (401/403), sem SDK, sem CLI de inferência open-source, sem exemplo de comunidade com parsing real. **O exemplo oficial sequer faz streaming** (`print(response.text)` sem `stream=True`).

| Achado | Confiança |
|---|---|
| `streaming:true` existe e "entrega em tempo real" | Confirmado-oficial (insuficiente) |
| Resposta não-streaming: `{message, stop_reason, tokens, conversation_id}` | Confirmado-oficial |
| Shape do evento `data:` (JSON vs texto), incremental vs cumulativo, `[DONE]`, entrega do `conversation_id` em stream | **Desconhecido** |

**Estratégia defensiva adotada no código** (`adapters/stackspot/stream.py`):
- Detectar `Content-Type` da resposta; se `application/json` (servidor bufferizou), cair no caminho não-streaming e re-emitir como 1 chunk.
- Para `text/event-stream`: por linha `data:`, `strip`; se `[DONE]` → fim; tentar `json.loads` e procurar texto em `message`/`answer`/`content`/`delta`/`text`/`choices[0].delta.content`; se não for JSON, tratar como texto puro.
- **Auto-detectar incremental vs cumulativo:** se o novo texto `startswith` o acumulado, é cumulativo → emitir só o sufixo; senão incremental → emitir o chunk.
- Capturar `stop_reason`/`tokens`/`conversation_id` do chunk final quando presentes.

**Validar no corp env:** `curl -N -H "Accept: text/event-stream" ... -d '{"streaming":true,...}'`, salvar cru; confirmar Content-Type, shape do `data:`, incremental vs cumulativo, existência de `[DONE]`, e em qual chunk vem o `conversation_id`. Tentar `GET /openapi.json` **com** Bearer.

---

## OQ-5 — Token OAuth e `realm` · ✅ em grande parte resolvido

| Achado | Confiança |
|---|---|
| `POST https://idm.stackspot.com/{realm}/oidc/oauth/token`, `grant_type=client_credentials`, form-urlencoded | Confirmado-oficial/comunidade |
| **`{realm}` = slug da conta** (NÃO o literal "stackspot"); vale p/ Freemium e Enterprise; copiado do portal "Access Token" | Confirmado-oficial |
| **Token expira em 1200s (20 min)** | Confirmado-oficial |
| Resposta lê comprovadamente `access_token`; `expires_in`/`token_type`/`scope` são padrão OIDC | `access_token` Confirmado; resto Inferido |
| `refresh_token` não se aplica a client_credentials | Inferido (padrão) |

**Decisões aplicadas no código:** `realm` é **configurável e sem default enganoso** (era "stackspot"); TTL default = **1200s**, mas `expires_in` da resposta tem prioridade quando presente; refresh ~60s antes.
**Validar no corp env:** um `curl` real do token → inspecionar JSON cru (`expires_in`, `token_type`, `scope`) e confirmar o realm Enterprise no portal.

---

## OQ-3 — Listagem de agents · ✅ resolvido (config manual)

Não há endpoint público de listagem de agents; `agentId` é copiado da URL do agent no portal. Catálogo do GAMBI é **config-driven** (já implementado, `ConfigAgentCatalog`).
**Validar no corp env:** inspecionar a aba Network do Portal AI Enterprise ao abrir a tela de agents — pode haver endpoint interno (`.../v1/agents`) não documentado que permitiria `/v1/models` dinâmico.

---

## OQ-6 — Valores de `stop_reason` · ⚠️ só "stop" documentado

A doc só mostra `"stop"`; nenhum outro valor enumerado. **Defensivo (já no código):** `"stop"`→`stop`; desconhecido→`stop` + log. Hipóteses provisionadas: `length`/`max_tokens`→`length`; `content_filter`→`content_filter`.
**Validar no corp env:** forçar truncamento (max baixo), filtro de conteúdo e tool-call; catalogar os `stop_reason` reais.
