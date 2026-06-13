# Mapeamento OpenAI ↔ StackSpot

Este é o **domínio do GAMBI**. Tabela de tradução entre o protocolo OpenAI Chat Completions e a Agents API do StackSpot, com as decisões de design e suas perguntas abertas.

> Nada aqui é contrato fechado: linhas marcadas com ⚠️ dependem de PERGUNTAS ABERTAS (ver [README](README.md#perguntas-abertas-consolidadas-bloqueiam-decisões-de-design)). Confirmar contra a API real.

## Endpoint

| OpenAI | StackSpot |
|---|---|
| `POST /v1/chat/completions` | `POST genai-inference-app.stackspot.com/v1/agent/{agentId}/chat` |
| `POST /v1/completions` (legacy) | idem (degradar para `user_prompt`) |
| `GET /v1/models` | ⚠️ sem equivalente — GAMBI inventa a lista (= agents disponíveis?) |

## Request: OpenAI → StackSpot

| Campo OpenAI | Campo StackSpot | Observação |
|---|---|---|
| `model` | `{agentId}` na URL | ⚠️ **Decisão central:** `model` identifica o **agent**, não um LLM. Ver abaixo. |
| `messages[]` | `user_prompt` (+ `conversation_id`/`use_conversation`) | ⚠️ OpenAI é stateless (manda histórico todo); StackSpot é stateful (`conversation_id`). Ver "Histórico". |
| `messages[].role: "system"` | — | ⚠️ System prompt é fixo no agent. Mensagem `system` do cliente não tem destino óbvio — prefixar no `user_prompt`? Ignorar? |
| `stream` | `streaming` | Mapeamento direto. |
| `temperature`, `top_p`, `max_tokens`, `frequency_penalty`, `presence_penalty` | — | ⚠️ Sem destino na Agents API (fixos no agent). Ignorar + logar, ou rejeitar. |
| `tools` / `tool_choice` / `functions` | — | ⚠️ Tools são configuradas no agent (toolkits), não passadas por request. Provável: não suportar function-calling no MVP. |
| `n`, `logprobs`, `stop`, `seed`, `response_format` | — | ⚠️ Sem equivalente conhecido. |
| (conteúdo de arquivo/imagem em `messages`) | `upload_ids[]` | Via fluxo de upload ([03](03-upload-files.md)); fora do MVP. |
| `user` | `execution_tag`? | Só existe em Quick Commands, não na Agents API. |

## Response: StackSpot → OpenAI (modo REST)

| Campo StackSpot | Campo OpenAI |
|---|---|
| `message` | `choices[0].message.content` (`role: "assistant"`) |
| `stop_reason` | `choices[0].finish_reason` ⚠️ (mapear valores — só `stop` conhecido) |
| `tokens.user` (+ `tokens.enrichment`?) | `usage.prompt_tokens` ⚠️ |
| `tokens.output` | `usage.completion_tokens` |
| `tokens.user + enrichment + output` | `usage.total_tokens` |
| `conversation_id` | ⚠️ sem campo OpenAI — GAMBI guarda internamente (ver Histórico) |
| `knowledge_source_id`, `source`, `tools_id` | descartar ou expor em campo de extensão custom |

Envelope OpenAI a montar: `id`, `object: "chat.completion"`, `created`, `model` (eco do agent), `choices[]`, `usage`.

## Response: streaming (SSE)

⚠️ **BLOQUEIO.** OpenAI emite chunks `chat.completion.chunk` com `choices[].delta.content` e termina com `data: [DONE]`. O formato do SSE do StackSpot **não está documentado** ([02](02-agents-api.md)). Sem capturar um stream real, não dá para escrever o tradutor de streaming. **Tarefa de spike obrigatória antes de implementar `stream: true`.**

## Decisão central: `model` → agent

O StackSpot não aceita `model` por request; cada **agent** encapsula (modelo + system prompt + KS + tools). Logo o campo `model` da OpenAI deve **selecionar o agent**. Opções:

- **A)** `model` = `agentId`/slug do StackSpot, repassado direto. Simples; vaza IDs do StackSpot ao cliente.
- **B)** GAMBI mantém um mapa `nome-amigável → agentId` (config). Cliente usa `"model": "meu-assistente"`. Mais limpo; exige config.
- **C)** Um agent default + `model` ignorado. Mínimo; inflexível.

→ Recomendação inicial: **(B)**, com `GET /v1/models` listando os nomes amigáveis configurados. Decidir na spec.

## Decisão: histórico (stateless ↔ stateful)

OpenAI manda `messages[]` inteiro a cada chamada (stateless). StackSpot mantém estado por `conversation_id`. Opções:

- **A)** Stateless puro: a cada request, serializar `messages[]` num único `user_prompt` (com marcações de papel) e **não** usar `conversation_id`. Fiel ao modelo OpenAI; perde recursos de conversa do StackSpot; prompts podem ficar grandes.
- **B)** Stateful: GAMBI mapeia conversa → `conversation_id`, manda só a última mensagem do usuário. Aproveita o StackSpot; exige store de mapeamento e lidar com divergência de histórico.

→ Recomendação inicial p/ MVP: **(A)** (stateless), por ser determinística e casar com o contrato OpenAI. Reavaliar com base nas respostas das perguntas abertas de conversa.

## Tradução de erros

⚠️ Formato de erro do StackSpot não documentado. O GAMBI deve mapear para o envelope de erro OpenAI (`{ "error": { "message", "type", "code" } }`) e traduzir status (401, 429, 5xx). Definir na spec a partir de observação real.

## Resumo de prioridades para a spec

1. Resolver o **formato SSE** (spike) — destrava streaming.
2. Fechar a **estratégia `model` → agent** (opção B).
3. Fechar a **estratégia de histórico** (opção A no MVP).
4. Definir política para parâmetros LLM não suportados (ignorar+logar).
5. Definir mapeamento de erros e de `finish_reason`.
