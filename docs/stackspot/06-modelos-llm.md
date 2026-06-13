# Modelos LLM no StackSpot AI

Fonte: [LLM Models](https://ai.stackspot.com/docs/agents/llm-models) e [Create Agents](https://ai.stackspot.com/docs/agents/create-agents)

## Modelos disponíveis (lista da doc)

**OpenAI:**
- GPT-4.1, GPT-4.1 mini, GPT-4.1 nano
- GPT-4o, GPT-4o mini
- GPT-5, GPT-5 mini, GPT-5 nano
- GPT o3 mini, GPT o4 mini

**Anthropic Claude (via Bedrock):**
- Claude 3.5 Sonnet
- Claude 3.7 Sonnet
- Claude 4 Sonnet

**Outros (via Bedrock, salvo Gemini):**
- DeepSeek R1
- Llama 4 Maverick, Llama 4 Scout
- Mistral Pixtral
- Gemini 2.5 Pro

> A lista muda com o tempo; reconfirmar na doc antes de fixar qualquer mapeamento.

## Como o modelo é selecionado

O modelo é escolhido **na configuração do agent** (UI), junto com os parâmetros LLM. **Não** é passado na chamada da API ([02](02-agents-api.md) não tem campo `model`).

Parâmetros LLM definidos na criação do agent:

| Parâmetro | Faixa | Default |
|---|---|---|
| Temperature | 0 – 2.0 | 0.7 |
| Top P | 0 – 1.0 | — |
| Frequency Penalty | -2.0 – 2.0 | — |
| Presence Penalty | -2.0 – 2.0 | — |

Outros campos do agent: nome, **System prompt** (máx. 8.000 chars), Knowledge Sources (com threshold de relevância), Tools/Toolkits (até ~20), e configurações avançadas (modo conversacional, autonomia, planejador).

> Nota da doc: "Autonomy modes are turned off when the Agent is accessed via an API or Quick Command" — agents acessados via API não usam modos de autonomia.

## Implicações para o GAMBI (o ponto-chave)

Na OpenAI, o cliente escolhe o modelo e os parâmetros **por request** (`model`, `temperature`, `max_tokens`, ...). No StackSpot, **isso é fixo no agent** e o request só carrega `user_prompt`. Consequências:

1. O campo **`model`** da OpenAI **não** pode virar um modelo StackSpot diretamente — ele deve virar o **`agentId`** (cada agent encapsula modelo+prompt+KS). Ver [07](07-mapeamento-openai-stackspot.md).
2. Parâmetros como `temperature`, `top_p`, `max_tokens`, `frequency_penalty`, `presence_penalty` enviados pelo cliente OpenAI **não têm para onde ir** na Agents API. O GAMBI terá que **ignorá-los** (e logar/avisar) ou rejeitá-los. Decisão de design.
3. `stream` da OpenAI ↔ `streaming` do StackSpot — mapeamento direto (pendente do formato SSE).

## Perguntas abertas

- **Existe slug/ID de modelo usável via API?** A doc não mostra. Aparentemente não — o modelo é interno ao agent.
- **Agent pode ser criado/configurado via API?** A doc só descreve criação via UI; não há endpoint confirmado. Se não houver, os agents precisam ser pré-criados manualmente e o GAMBI apenas os consome.
- **Onde encontrar o `agentId`/slug** de um agent criado.
