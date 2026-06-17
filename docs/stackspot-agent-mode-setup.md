# Setup StackSpot — Agents por LLM (ASK + AGENT/EDIT)

> **Isto é setup no portal do StackSpot, não código.** Cole o System Prompt no campo de instruções e,
> quando indicado, o JSON Schema no campo *Structure output* (Advanced Settings).

## 0. Os DOIS agents por LLM (visão geral) — leia primeiro

Para **cada LLM** que você quer expor (ex.: `stackspot-llm-5.1`), crie **dois agents StackSpot**, porque
o modo do chat no VS Code muda o que o GAMBI precisa:

| Agent | Atende | Structure output | System prompt | No `gambi.agents.json` |
|---|---|---|---|---|
| **ASK** | ask mode (sem tools) | **DESLIGADO** | chat/assistente (texto/markdown) — ver §0.1 | `modes.ask` + `structured_output:false` |
| **AGENT/EDIT** | edit + agent (com tools) | **LIGADO** (schema da §1) | contrato de agent mode — ver §2 | `modes.agent` + `structured_output:true` |

Por que separados: o agent AGENT/EDIT tem Structured Output **ligado** → responde **sempre** JSON (ótimo p/
tool calling, péssimo p/ chat). O agent ASK tem Structured Output **desligado** → responde **texto/markdown**
normal. Misturar quebra um dos modos. O GAMBI roteia automaticamente (sem tools→ask; com tools→agent) — ver
`README` ("Um modelo, vários agents por modo").

### 0.1. System Prompt do agent **ASK** (Structure output = DESLIGADO)

```text
Você é um assistente de programação. Suas instruções de papel, tom e domínio vêm na própria entrada:
quando a conversa trouxer marcadores [Sistema]/[Usuário]/[Assistente], as mensagens [Sistema] definem
seu papel — adote-as como suas instruções. (Numa pergunta de turno único, a entrada pode vir como texto
cru, sem marcadores; nesse caso responda direto.)

REGRAS DE FORMATO:
- Responda em markdown claro e direto; use blocos de código com a linguagem correta (```python, ```bash...).
- Responda no MESMO idioma da pergunta do usuário.
- NÃO use JSON nem nenhum envelope estruturado — apenas a resposta em texto/markdown.
- Seja objetivo: explique o essencial, mostre código aplicável, evite encher linguiça.
```
> No portal, **deixe o "Structure output" DESLIGADO** neste agent. Este prompt também é neutro: a persona
> vem do `[Sistema]`. Se quiser uma regra transversal pra todos os usos, adicione um bloco curto ao final.

---

O restante deste doc (§1–§5) configura o agent **AGENT/EDIT** (o estruturado).

## 1. JSON Schema para o campo "Structure output" (agent AGENT/EDIT)

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
Você responde SEMPRE no formato JSON definido no schema configurado — é o seu único formato de
saída, em qualquer situação. Suas instruções de papel, tom e domínio vêm na própria entrada (ver
[Sistema] abaixo); siga-as para o CONTEÚDO, mas nunca quebre o formato JSON.

A ENTRADA pode conter, nesta ordem, seções demarcadas:
1) "## FERRAMENTAS DISPONÍVEIS" — as ferramentas que você PODE chamar NESTA requisição. Cada item traz:
     - nome: <identificador exato a usar em tool_calls[].name>
     - descrição: <o que faz>
     - argumentos: <JSON Schema dos argumentos esperados>
   Esta lista MUDA a cada requisição. Use SOMENTE o que estiver aqui; nunca invente ferramentas.
   Se a seção não existir ou vier vazia, você NÃO tem ferramentas → responda action="final".
2) "## CONVERSA" — o histórico, com marcadores [Sistema]/[Usuário]/[Assistente].
   A última mensagem [Usuário] é o pedido atual. As mensagens [Sistema] definem seu papel,
   tom e domínio — adote-as como suas instruções.
3) "## RESULTADOS DAS FERRAMENTAS" (só em continuações) — o resultado das ferramentas que você pediu no
   passo anterior, cada um como:
     - name: <nome da ferramenta>
       result: <saída/observação>
   Use-os para decidir o próximo passo.

A SAÍDA é inegociável — sempre e SOMENTE um objeto JSON conforme o schema; NUNCA escreva texto fora dele:
- Precisa usar ferramenta(s)? →
    action = "tool_call"
    tool_calls = [{ "name": "<nome exato da lista>", "arguments_json": "<string JSON conforme o schema da ferramenta>" }]
    content = ""
- Já pode responder sem ferramentas? →
    action = "final"
    content = "<resposta em markdown>"
    tool_calls = []
- Após "## RESULTADOS DAS FERRAMENTAS", continue: chame outra ferramenta (action=tool_call) ou finalize (action=final).
```

Este prompt é **neutro de propósito**: não afirma identidade própria nem menciona o proxy — só fixa o
contrato de **formato** (entrada/saída). A persona (papel, tom, domínio) vem das mensagens `[Sistema]`
que o cliente injeta, então o **mesmo** agent estruturado serve qualquer agent custom do VS Code.
Se você quiser uma regra **transversal** que valha pra todos (ex.: "sempre prefira a stack X"), adicione
um bloco curto ao final — mas evite afirmar uma persona única aqui, senão ela compete com a do `[Sistema]`.

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

## 3. Onde colar no portal + registrar no GAMBI
- **System prompt:** campo de instruções do agent (máx. 8.000 chars).
- **Structure output:** Advanced Settings → ative "Structure output" → cole o JSON do passo 1.
- Salve como um **agent novo** (não sobrescreva seu agent de chat).
- **No GAMBI** (`gambi.agents.json`): registre esse agent com **`"structured_output": true`** — assim o
  GAMBI bufferiza e parseia a saída mesmo em ask mode (sem isso, em ask mode o JSON vazaria cru). Ex.:
  `{"model_id":"stackspot-dev-agent","agent_id":"<id>","structured_output":true}`.
- **Recomendado — um modelo só, roteado por modo:** em vez de expor um agent separado para agent mode, use a
  forma `modes` para que o VS Code veja **um único** `stackspot-llm-5.1` e o GAMBI escolha o agent pelo modo
  (sem tools = ask; com tools = agent/edit). Ver `README` ("Um modelo, vários agents por modo") e `gambi.agents.example.json`.
  Assim `ask` aponta para um agent de chat e `agent` para este agent estruturado.

## 4. Validação (OQ-7)
- ✅ **Resolvido (capturas 2026-06-15/16):** o JSON volta no campo **`message` como string**; no streaming
  o StackSpot **fragmenta o JSON char-a-char** (por isso o GAMBI chama não-streaming em modo estruturado).
  Tokens (`input`/`output`) e `stop_reason` conforme esperado.
- ✅ **A2 RESOLVIDO:** confirmada a emissão de **`action=tool_call`** (sem RESULTADOS no input):
  `{"action":"tool_call","tool_calls":[{"name":"createFile","arguments_json":"{\"path\":\"hello.py\",...}"}],"content":""}`.
  `arguments_json` é string JSON → mapeia direto pro `tool_calls[].function.arguments`. `action=final` idem.
  Validação reproduzível em `scripts/validar-agent-mode.sh`; regressão em `tests/unit/test_structured.py`.

## 5. A metade em código do GAMBI — ✅ IMPLEMENTADA (2026-06-15)
Já está no código:
- **Injeta** no `user_prompt` a seção "FERRAMENTAS DISPONÍVEIS" a partir do array `tools` do VS Code,
  além de "CONVERSA" e "RESULTADOS DAS FERRAMENTAS" (`gambi/domain/flattener.py`).
- **Parseia** o JSON do `message` (`gambi/domain/structured.py`): `action=tool_call` → `tool_calls` OpenAI
  (`name`→`function.name`, `arguments_json`→`function.arguments`), `finish_reason="tool_calls"`;
  `action=final` → `content`. **Fallback:** se a resposta não for o nosso JSON, vira texto normal.
- **Loop**: o VS Code executa a tool e devolve `role:"tool"`; o GAMBI já formata isso em
  "RESULTADOS DAS FERRAMENTAS" no próximo turno (o StackSpot não tem papel `tool`).
- Em agent mode o GAMBI chama o StackSpot **não-streaming** (precisa do JSON inteiro) e entrega ao
  VS Code em SSE ou JSON conforme o `stream` do request.

- **Robustez (G):** se o agent furar o schema, o GAMBI faz 1 *repair retry* (reprompt "responda só o JSON")
  antes do fallback p/ texto. E a flag **`structured_output`** garante parse mesmo sem tools (ask mode).

> **Premissa confirmada (OQ-7):** o JSON estruturado vem em `message` (string) — validado por captura.
> Resta validar a emissão de `action=tool_call` (passo 4, A2).

## Restrições honestas
- Argumentos corretos dependem do agent seguir o schema da ferramenta **injetado no prompt** — o structured
  output garante o **invólucro** (action/tool_calls/content), não a perfeição dos argumentos.
- É um **agent dedicado**; o de chat continua sem structured output.
- Streaming "de verdade" provavelmente não no fluxo de tool-call (precisamos do JSON completo).
