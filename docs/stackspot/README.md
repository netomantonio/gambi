# StackSpot AI — Referência para o GAMBI

Documentação destilada da [doc oficial do StackSpot AI](https://ai.stackspot.com/docs/) para servir de base ao GAMBI (proxy OpenAI-compatible → agents StackSpot).

> **Regra deste diretório:** o que está aqui foi extraído da documentação oficial. Tudo que a doc **não cobre** está marcado como `PERGUNTA ABERTA` — não trate suposição como contrato. Confirme contra a API real antes de implementar.
>
> Coletado em 2026-06-13. A doc do StackSpot muda; reconfirme hosts e payloads antes de codar o adapter.

## Índice

| Arquivo | Conteúdo | Relevância p/ GAMBI |
|---|---|---|
| [01-autenticacao.md](01-autenticacao.md) | OAuth client_credentials, PAT vs Service Credential, realm | **Crítica** — todo request precisa do Bearer token |
| [02-agents-api.md](02-agents-api.md) | `POST /v1/agent/{agentId}/chat`: request, response REST, streaming SSE | **Crítica** — é o coração da tradução |
| [03-upload-files.md](03-upload-files.md) | Upload de arquivos p/ contexto (`upload_ids`) | Média — mapeável a anexos/multimodal |
| [04-knowledge-sources-api.md](04-knowledge-sources-api.md) | CRUD de Knowledge Sources via API | Baixa — fora do caminho OpenAI básico |
| [05-remote-quick-commands.md](05-remote-quick-commands.md) | API assíncrona de Quick Commands (create-execution + polling) | Média — modelo alternativo de execução |
| [06-modelos-llm.md](06-modelos-llm.md) | Modelos LLM disponíveis | **Crítica** — mapeia o campo `model` da OpenAI |
| [07-mapeamento-openai-stackspot.md](07-mapeamento-openai-stackspot.md) | Tabela de tradução OpenAI ↔ StackSpot + decisões de design | **Crítica** — é o domínio do GAMBI |

## Visão geral da integração

```
Cliente OpenAI                GAMBI (proxy)                    StackSpot AI
──────────────                ─────────────                    ────────────
POST /v1/chat/completions  →  traduz request          →  POST genai-inference-app.stackspot.com
  { model, messages,            (domínio: tradução)           /v1/agent/{agentId}/chat
    stream, ... }                                             { user_prompt, streaming, ... }
                                                       ←  resposta REST ou SSE
   resposta OpenAI         ←  traduz response          ←
   (ou stream SSE)             (domínio: tradução)
```

Dois hosts distintos aparecem na doc do StackSpot:

- **`genai-inference-app.stackspot.com`** — execução **síncrona** de agent (`/v1/agent/{agentId}/chat`). É o que mais se parece com `chat/completions`. **É o alvo primário do GAMBI.**
- **`genai-data-integration-api.stackspot.com`** + **`data-integration-api.stackspot.com`** — Quick Commands **assíncronos** (create-execution + polling por `execution_id`) e gestão de Knowledge Sources/uploads.

## Perguntas abertas consolidadas

> **Fonte canônica e graduada por evidência:** [`08-gaps-pesquisa.md`](08-gaps-pesquisa.md) (OQ-1..8 com status e capturas reais). Abaixo, só um snapshot.

**✅ Resolvidas (por captura real / pesquisa):**
- **OQ-1/OQ-7 — SSE e structured output:** o `message` volta como string; com `streaming:true` o StackSpot fragmenta o JSON char-a-char (por isso bufferizamos não-stream em modo estruturado/agent).
- **OQ-2 — contrato VS Code Custom Endpoint:** SSE OpenAI-padrão, sem `/v1/models` obrigatório, sem assinatura.
- **OQ-3/OQ-4 — seleção de agent:** `model` → `agentId` via catálogo config (sem API de listagem); alias por modo.
- **OQ-5 — realm/token:** `realm` = slug da conta; TTL 1200s (prioriza `expires_in`).
- **OQ-8 — detecção de modo:** 2-vias (sem tools=ask / com tools=agent); edit↔agent indistinguíveis (aceito).
- **A2 — agent mode ponta-a-ponta:** captura real confirmou `action=tool_call` (e `final`); `arguments_json` é string JSON. Agent mode validado.
- **tokens:** prompt em `input`, `user`/`enrichment` podem ser null.

**⏳ Ainda abertas (validar no corp env / fora do v1):**
- **OQ-6 — valores de `stop_reason`** além de `stop` (mapeamento defensivo por ora).
- **Multi-turno server-side** via `conversation_id` (v1 é stateless). → [02](02-agents-api.md).
- **Formato de erros** do StackSpot (status/corpo) — mapeamos defensivamente para o envelope OpenAI.
- **Rate limits da Agents API síncrona** (só há números p/ Quick Commands). → [05](05-remote-quick-commands.md).
- Itens fora do v1: `x-account-id`/upload ([03](03-upload-files.md)), criação de agent via API ([06](06-modelos-llm.md)).

## Fontes

- [Agents API](https://ai.stackspot.com/docs/agents/agent-api/agents-api)
- [Upload Files to Contextualize Agent Requests](https://ai.stackspot.com/docs/agents/agent-api/upload-files)
- [Create Agents](https://ai.stackspot.com/docs/agents/create-agents)
- [LLM Models](https://ai.stackspot.com/docs/agents/llm-models)
- [Create/Update KS via API](https://ai.stackspot.com/docs/knowledge-source/create-update-via-api)
- [Create and Execute Remote Quick Commands](https://ai.stackspot.com/docs/quick-commands/create-remote-qc)
