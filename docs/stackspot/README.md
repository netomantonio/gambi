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

## Perguntas abertas consolidadas (bloqueiam decisões de design)

Estas precisam ser respondidas contra a API real / suporte StackSpot antes de fechar o domínio:

1. **Formato exato dos eventos SSE** quando `streaming: true`. A doc só diz "entregue via Server-Sent Events" — não mostra o shape de cada `data:` chunk (campos, delta vs cumulativo, evento de término). → ver [02](02-agents-api.md). **É o maior bloqueio para o streaming OpenAU-compatible.**
2. **Como o cliente seleciona o agent.** O modelo LLM é fixado na criação do agent (UI); a chamada não recebe `model`. O `agentId` vai na URL. Mapear o campo `model` da OpenAI → `agentId`/slug é decisão do GAMBI. → ver [06](06-modelos-llm.md) e [07](07-mapeamento-openai-stackspot.md).
3. **Semântica de `conversation_id` / `use_conversation` na API** (multi-turno). A página de chat-history documenta só a IDE. → ver [02](02-agents-api.md).
4. **Valor do `realm`** no endpoint de token: Freemium parece usar `stackspot`; Enterprise usa `{your_account_realm}`. Confirmar. → ver [01](01-autenticacao.md).
5. **Origem do `x-account-id`** exigido no upload form. → ver [03](03-upload-files.md).
6. **Criação de agent via API** — a doc descreve só criação via UI; existência de endpoint não confirmada. → ver [06](06-modelos-llm.md).
7. **Rate limits da Agents API síncrona** (`/v1/agent/.../chat`). A doc só publica limites de Quick Commands e PAT. → ver [05](05-remote-quick-commands.md).
8. **Formato de erros** (status codes, corpo) de todas as APIs — não documentado.
9. **Mapeamento de `stop_reason`** do StackSpot para `finish_reason` da OpenAI — valores possíveis além de `stop` desconhecidos.

## Fontes

- [Agents API](https://ai.stackspot.com/docs/agents/agent-api/agents-api)
- [Upload Files to Contextualize Agent Requests](https://ai.stackspot.com/docs/agents/agent-api/upload-files)
- [Create Agents](https://ai.stackspot.com/docs/agents/create-agents)
- [LLM Models](https://ai.stackspot.com/docs/agents/llm-models)
- [Create/Update KS via API](https://ai.stackspot.com/docs/knowledge-source/create-update-via-api)
- [Create and Execute Remote Quick Commands](https://ai.stackspot.com/docs/quick-commands/create-remote-qc)
