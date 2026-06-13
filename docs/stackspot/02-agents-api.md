# Agents API — execução síncrona

**É o endpoint central do GAMBI.** Executa um agent (com seu modelo/prompt/KS já configurados) e retorna a resposta — em modo REST ou streaming SSE.

Fonte: [Agents API](https://ai.stackspot.com/docs/agents/agent-api/agents-api)

## Endpoint

```
POST https://genai-inference-app.stackspot.com/v1/agent/{agentId}/chat
Authorization: Bearer <JWT>
Content-Type: application/json
```

- `{agentId}` identifica o agent. **PERGUNTA ABERTA:** a doc não diz onde encontrar o `agentId`/slug após criar o agent, nem se aceita slug ou ID. Confirmar.

## Request body

| Campo | Tipo | Descrição |
|---|---|---|
| `user_prompt` | string | Prompt/pergunta do usuário. **Obrigatório.** |
| `streaming` | boolean | `true` → resposta via SSE em tempo real; `false` → resposta REST única. |
| `stackspot_knowledge` | boolean | Usa as Knowledge Sources globais do StackSpot. |
| `return_ks_in_response` | boolean | Inclui na resposta os IDs das KS efetivamente usadas. |
| `use_conversation` | boolean | Mantém contexto multi-turno da conversa. |
| `conversation_id` | string | ID p/ continuar uma conversa anterior (formato ULID, ex: `01K9T3D5752EMVMDJTSEW536AP`). |
| `upload_ids` | string[] | IDs de arquivos enviados p/ contexto. Ver [03-upload-files.md](03-upload-files.md). |

Exemplo:

```json
{
  "streaming": true,
  "user_prompt": "What is an API?",
  "stackspot_knowledge": true,
  "return_ks_in_response": false,
  "use_conversation": true,
  "conversation_id": "01K9T3D5752EMVMDJTSEW536AP"
}
```

> **PERGUNTA ABERTA:** o body **não tem campo `model`** nem parâmetros LLM (temperature, top_p, max_tokens). Esses são fixados na configuração do agent. Isso é central para o GAMBI — ver [06-modelos-llm.md](06-modelos-llm.md) e [07-mapeamento-openai-stackspot.md](07-mapeamento-openai-stackspot.md).
>
> Tipo de `stackspot_knowledge`: o exemplo da doc mostra ora boolean (`true`), ora string (`"true"`). Confirmar o tipo aceito.

## Response — modo REST (`streaming: false`)

```json
{
  "message": "string",
  "stop_reason": "stop",
  "tokens": {
    "user": 0,
    "enrichment": 0,
    "output": 0
  },
  "upload_ids": {},
  "knowledge_source_id": [],
  "source": [],
  "cross_account_source": [],
  "tools_id": [],
  "conversation_id": "string"
}
```

| Campo | Significado | Mapeia p/ OpenAI |
|---|---|---|
| `message` | texto gerado pelo agent | `choices[0].message.content` |
| `stop_reason` | motivo de término (ex: `stop`) | `choices[0].finish_reason` |
| `tokens.user` | tokens do prompt do usuário | parte de `usage.prompt_tokens` |
| `tokens.enrichment` | tokens gastos em enriquecimento (KS/contexto) | sem equivalente direto — somar a prompt? |
| `tokens.output` | tokens da resposta | `usage.completion_tokens` |
| `conversation_id` | ID da conversa (p/ continuar depois) | sem equivalente — gerenciar no GAMBI |
| `knowledge_source_id`, `source`, `tools_id` | rastreabilidade de KS/tools usados | sem equivalente OpenAI padrão |

> **PERGUNTA ABERTA:** valores possíveis de `stop_reason` além de `stop` (ex: limite de tokens, filtro de conteúdo) — necessários p/ mapear `finish_reason` corretamente.

## Response — modo streaming (`streaming: true`)

A doc afirma apenas que a resposta é entregue em tempo real via **Server-Sent Events (SSE)**.

> **PERGUNTA ABERTA (crítica):** o formato exato de cada evento SSE não está documentado:
> - Estrutura de cada `data:` (JSON? texto puro?)
> - Os deltas são incrementais (só o pedaço novo) ou cumulativos?
> - Existe evento de término (`[DONE]`? um chunk final com `stop_reason`/`tokens`)?
> - Como `conversation_id` é entregue no streaming?
>
> **Isto bloqueia o streaming OpenAI-compatible** (`chat.completion.chunk`). Precisa ser observado contra a API real (capturar um SSE bruto) antes de implementar o adapter de streaming. Tratar como tarefa de spike/investigação.

## Multi-turno / histórico

- `use_conversation: true` + `conversation_id` mantêm o contexto entre chamadas.
- A página [chat-history](https://ai.stackspot.com/docs/agents/chat-history) documenta apenas a experiência na IDE (visualizar/continuar/deletar conversas por data), **não a API**.

> **PERGUNTA ABERTA:** semântica completa da conversa via API: existe endpoint p/ recuperar histórico? Quem cria o `conversation_id` na primeira chamada (o cliente ou o servidor)? TTL da conversa? Como o GAMBI mapeia o array `messages` da OpenAI (que carrega todo o histórico) para esse modelo baseado em `conversation_id`?

## Implicações para o GAMBI

- `genai-inference-app.stackspot.com/v1/agent/{agentId}/chat` é o destino primário do `POST /v1/chat/completions`.
- A maior incógnita técnica é o **formato do SSE** — priorizar um spike para capturá-lo.
- Decisão de domínio: OpenAI envia o histórico inteiro em `messages` a cada request (stateless); StackSpot usa `conversation_id` (stateful). O GAMBI precisa escolher uma estratégia — ver [07](07-mapeamento-openai-stackspot.md).
