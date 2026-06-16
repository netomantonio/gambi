# Setup StackSpot — Agent dedicado a "agent mode" (Structured Output + System Prompt)

> **Isto é setup no portal do StackSpot, não código.** Cole o JSON Schema no campo *Structure output*
> (Advanced Settings) e o system prompt no campo de instruções do agent. Objetivo: que o agent emita
> **sempre** um JSON previsível que o GAMBI traduz em `tool_calls` OpenAI → habilita o agent mode do VS Code.
>
> ⚠️ Use isto num **agent dedicado** (ex.: `stackspot-dev-agent`), separado do seu agent de chat normal —
> porque com structured output o agent **sempre** responde JSON (não serve pra chat em texto puro).
>
> ⚠️ Status: depende de validar a **OQ-7** (como o structured output volta na API / streaming) — ver
> `docs/stackspot/08-gaps-pesquisa.md`. Este doc é o lado StackSpot; a metade em código do GAMBI
> (injetar tools no prompt, parsear, montar `tool_calls`, loop de resultado) vem **depois** da validação.

## 1. JSON Schema para o campo "Structure output"

Genérico de propósito (não enumera ferramentas — elas vêm no prompt em runtime). Os `arguments` vão como
**string JSON** (igual ao `tool_calls[].function.arguments` da OpenAI), o que evita problemas de strict mode
e mapeia direto para o formato OpenAI.

```json
{
  "name": "gambi_agent_response",
  "strict": true,
  "schema": {
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "action": {
        "type": "string",
        "enum": ["tool_call", "final"],
        "description": "tool_call = precisa executar uma ferramenta; final = resposta pronta"
      },
      "content": {
        "type": "string",
        "description": "Resposta final em markdown quando action=final; string vazia caso contrário"
      },
      "tool_calls": {
        "type": "array",
        "description": "Ferramentas a executar quando action=tool_call; lista vazia caso contrário",
        "items": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "name": {
              "type": "string",
              "description": "Nome EXATO de uma ferramenta da lista FERRAMENTAS DISPONÍVEIS"
            },
            "arguments_json": {
              "type": "string",
              "description": "Argumentos como STRING JSON válida, conforme o schema da ferramenta"
            }
          },
          "required": ["name", "arguments_json"]
        }
      }
    },
    "required": ["action", "content", "tool_calls"]
  }
}
```

> O portal pode pedir só o objeto `schema` (sem o wrapper `name`/`strict`), ou o wrapper inteiro —
> **ajuste ao que o campo aceitar** e confirme clicando em "Examples" pra ver o formato esperado.

## 2. System Prompt (≤ 8.000 caracteres)

```text
Você é um agent acessado via API por um proxy (GAMBI) que integra o VS Code Copilot Chat.

COMO VOCÊ RECEBE A ENTRADA (contrato de entrada):
O texto que você recebe (user_prompt) é montado pelo GAMBI e pode conter, nesta ordem, seções demarcadas:
1) "## FERRAMENTAS DISPONÍVEIS" — as ferramentas que você PODE chamar NESTA requisição. Cada item traz:
     - nome: <identificador exato a usar em tool_calls[].name>
     - descrição: <o que faz>
     - argumentos: <JSON Schema dos argumentos esperados>
   Esta lista MUDA a cada requisição. Use SOMENTE o que estiver aqui; nunca invente ferramentas.
   Se a seção não existir ou vier vazia, você NÃO tem ferramentas → responda action="final".
2) "## CONVERSA" — o histórico, com marcadores [Sistema]/[Usuário]/[Assistente].
   A última mensagem [Usuário] é o pedido atual.
3) "## RESULTADOS DAS FERRAMENTAS" (só em continuações) — o resultado das ferramentas que VOCÊ pediu no
   passo anterior, cada um como:
     - name: <nome da ferramenta>
       result: <saída/observação>
   Use-os para decidir o próximo passo.

COMO VOCÊ RESPONDE (contrato de saída — inegociável):
- SEMPRE e SOMENTE um objeto JSON conforme o schema configurado. NUNCA escreva texto fora do JSON.
- Precisa usar ferramenta(s)? →
    action = "tool_call"
    tool_calls = [{ "name": "<nome exato da lista>", "arguments_json": "<string JSON conforme o schema da ferramenta>" }]
    content = ""
- Já pode responder sem ferramentas? →
    action = "final"
    content = "<resposta em markdown>"
    tool_calls = []
- Após "## RESULTADOS DAS FERRAMENTAS", continue: chame outra ferramenta (action=tool_call) ou finalize (action=final).

COMPORTAMENTO (ajuste ao seu domínio):
- [coloque aqui as regras do seu agent: stack, convenções, tom, limites]
```

Personalize o bloco COMPORTAMENTO — é onde você "amarra" o que quer.

### 2b. Formato exato que o GAMBI vai injetar no `user_prompt`
O system prompt acima descreve este contrato; a metade em código do GAMBI (passo 5) deve montar a entrada
exatamente assim, para o agent saber parsear:

```text
## FERRAMENTAS DISPONÍVEIS
- nome: createFile
  descrição: Cria um arquivo novo com o conteúdo dado.
  argumentos: {"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}
- nome: runInTerminal
  descrição: Executa um comando no terminal.
  argumentos: {"type":"object","properties":{"command":{"type":"string"}},"required":["command"]}

## CONVERSA
[Usuário] crie um arquivo hello.py que imprime olá

## RESULTADOS DAS FERRAMENTAS
- name: createFile
  result: arquivo hello.py criado com sucesso
```

(A seção FERRAMENTAS vem da array `tools` do VS Code; a CONVERSA, do `messages`; os RESULTADOS, das mensagens
`role:"tool"` que o VS Code devolve após executar uma `tool_call`. Tudo montado pelo GAMBI — ver passo 5.)

## 3. Onde colar no portal
- **System prompt:** campo de instruções do agent (máx. 8.000 chars).
- **Structure output:** Advanced Settings → ative "Structure output" → cole o JSON do passo 1.
- Salve como um **agent novo** (não sobrescreva seu agent de chat).

## 4. Validação (responde a OQ-7 — capture e me mande)
Com o agent criado, chame via API e capture:
1. **Onde o JSON volta:** o campo `message` da resposta vira a **string JSON** do schema? Há campo separado?
   ```bash
   curl -sN ".../v1/agent/<id-do-agent-structured>/chat" -H "Authorization: Bearer $JWT" \
     -H "Content-Type: application/json" \
     -d '{"streaming": false, "user_prompt": "diga olá", "stackspot_knowledge": false}'
   ```
2. **Confiabilidade:** rode ~5-10 prompts variados — ele respeita o schema sempre? Em quais modelos LLM?
3. **Com streaming (`streaming: true`):** o JSON vem fragmentado nos frames `data:` (parcial) ou só inteiro no fim?

## 5. A metade em código do GAMBI — ✅ IMPLEMENTADA (2026-06-15)
Já está no código (pendente só de validar a premissa de onde o JSON volta — ver "Premissa" abaixo):
- **Injeta** no `user_prompt` a seção "FERRAMENTAS DISPONÍVEIS" a partir do array `tools` do VS Code,
  além de "CONVERSA" e "RESULTADOS DAS FERRAMENTAS" (`gambi/domain/flattener.py`).
- **Parseia** o JSON do `message` (`gambi/domain/structured.py`): `action=tool_call` → `tool_calls` OpenAI
  (`name`→`function.name`, `arguments_json`→`function.arguments`), `finish_reason="tool_calls"`;
  `action=final` → `content`. **Fallback:** se a resposta não for o nosso JSON, vira texto normal.
- **Loop**: o VS Code executa a tool e devolve `role:"tool"`; o GAMBI já formata isso em
  "RESULTADOS DAS FERRAMENTAS" no próximo turno (o StackSpot não tem papel `tool`).
- Em agent mode o GAMBI chama o StackSpot **não-streaming** (precisa do JSON inteiro) e entrega ao
  VS Code em SSE ou JSON conforme o `stream` do request.

> **Premissa a validar (OQ-7):** o parser assume que o JSON estruturado vem no campo `message` da
> resposta. Se a captura real mostrar outro lugar, muda-se **um ponto** (`reply.message` no use case).
> Falta também medir confiabilidade do schema e comportamento com streaming ligado.

## Restrições honestas
- Argumentos corretos dependem do agent seguir o schema da ferramenta **injetado no prompt** — o structured
  output garante o **invólucro** (action/tool_calls/content), não a perfeição dos argumentos.
- É um **agent dedicado**; o de chat continua sem structured output.
- Streaming "de verdade" provavelmente não no fluxo de tool-call (precisamos do JSON completo).
