# Remote Quick Commands — execução assíncrona

Modelo **alternativo** ao Agents API: dispara uma execução e faz **polling** pelo resultado.
Assíncrono (não streaming, mas o callback expõe progresso por step → pseudo-streaming). É o caminho
para **eliminar o teto de ~120s do gateway** (não há conexão longa pendurada) e ganhar UX de raciocínio
+ orquestração multi-step. Ver o plano em `docs/gambi-roadmap.md` §9 (item L).

Fontes oficiais:
- [Create and Execute Remote Quick Commands](https://ai.stackspot.com/docs/quick-commands/create-remote-qc)
- [Remote Quick Command Example](https://ai.stackspot.com/docs/quick-commands/examples-qc/example-remote-qc) (JSON do callback verbatim)

> **Host CONFIRMADO (portal, aba "Como usar" do QC `agentrix-adk-create`, 2026-06-18):** create
> **e** callback ficam no MESMO host **`genai-code-buddy-api.stackspot.com`**. A doc oficial genérica
> cita `genai-data-integration-api.stackspot.com` p/ create — diverge; o portal por-QC é a fonte
> autoritativa da conta. ⇒ resolve a PERGUNTA ABERTA #2 (host).

## 1. Criar execução (CONFIRMADO)

```
POST https://genai-code-buddy-api.stackspot.com/v1/quick-commands/create-execution/{quick_command_slug}
Authorization: Bearer <access_token>
Content-Type: application/json
```
```json
{
  "input_data": "Your input data here",
  "execution_tag": "[opcional] tag",
  "upload_ids": ["lista de upload ids"]
}
```
Resposta: inclui um **`execution_id`**. *(PERGUNTA ABERTA: a resposta é o id cru ou um objeto JSON? O spike captura.)*

## 2. Polling do callback (shape CONFIRMADO pela doc de exemplo)

```
GET https://genai-code-buddy-api.stackspot.com/v1/quick-commands/callback/{execution_id}
Authorization: Bearer <access_token>
```

Exemplo **verbatim** da doc (execução COMPLETED):
```json
{
  "execution_id": "01HZ828C3K4E2093EYBABG014K",
  "quick_command_slug": "translate-english-to-spanish",
  "conversation_id": "01HZ828C3KXNTD8CQAWV056ZVG",
  "progress": {
    "start": "2024-05-31T19:33:03.731642+00:00",
    "end": "2024-05-31T19:33:09.141119+00:00",
    "duration": 5,
    "execution_percentage": 1.0,
    "status": "COMPLETED"
  },
  "steps": [
    {
      "step_name": "translate-english-to-spanish",
      "execution_order": 0,
      "type": "LLM",
      "step_result": { "answer": "Hola, ¿cómo estás? ...", "sources": [] }
    }
  ],
  "result": "Hi, how are you?... Hola, ¿cómo estás?..."
}
```

Fatos confirmados:
- **Saída por step:** cada `steps[]` tem `step_result.answer` (texto) + `sources` — é texto, como o `message` do agent.
- **Resposta final:** top-level `result` (no exemplo de 1 step, = answer do step).
- **Status:** `COMPLETED` (doc) e `FAILED` (busca). `execution_percentage` ∈ [0, 1.0]; completar = `1.0` + `COMPLETED`.
- **Multi-step + multi-tipo:** `steps[]` ordenado por `execution_order`; `type` (ex.: `LLM`). Encadeia passos/agents.
- **`conversation_id`** presente (multi-turno, como a Agents API).

## ⚠️ PERGUNTAS ABERTAS (o que o spike precisa cravar)

1. **Parcial durante RUNNING (o coração):** durante a execução (antes de COMPLETED), os `steps[].step_result.answer` aparecem **parciais/acumulados**? Um step ainda não terminado aparece com `step_result` null/parcial? *(Observação do usuário: SIM, snapshot por step acumulado — confirmar com captura ao vivo.)*
2. ~~**Host do callback**~~ **✅ RESOLVIDA (portal):** create + callback em `genai-code-buddy-api.stackspot.com`.
3. **Enum de status completo:** CREATED / RUNNING / COMPLETED / FAILED / outros?
4. **Intervalo de polling recomendado:** não documentado (busca sugere ~5s).
5. **QC emite structured output → `tool_calls`?** o `answer` de um step pode carregar nosso JSON `{"action":"tool_call",...}` (depende do prompt do QC). Decide se QC-async *substitui* o agent mode ou só *complementa*.

## Limites e retry (CONFIRMADOS)

- **Retry automático:** até 3 tentativas adicionais (4 no total) por passo de LLM. Não configurável.
- **Service Credential:** 20 requests/min, 6.000/dia. **Personal Access Token:** 100 requests / 24h (`HTTP 429`).
- ⚠️ **Polling divide essa cota.** A cada 3-5s, um job de 2 min = 24-40 GETs → perto do teto de 20/min do Service Credential. Exige cadência adaptativa/backoff. *(PERGUNTA ABERTA: se os limites valem para a Agents API síncrona — ver [01](01-autenticacao.md).)*

## Command Flow — QC é orquestração visual (confirmado no portal, 2026-06-18)

A aba "Command Flow" do `agentrix-adk-create` mostra um **canvas de automação multi-step**: blocos de
**Prompt**, **Web Request**, **Conditional** e **Execução Paralela**, ligados por caminhos de
sucesso/erro, de um `start` até um bloco de resultado. O `agentrix-adk-create` **gera e devolve na
resposta** o artefato de agent + skill + prompt (é um **gerador** — não provisiona nada na conta, sem
side-effect). Ou seja: Quick Commands são o **substrato de orquestração** (agents/steps atuando em
conjunto, fluxos paralelos/condicionais) — exatamente a visão do roadmap §9 (enriquecimento de KS em
tempo real, governança, validações, fluxos interconectados). Cada bloco do flow deve aparecer como um
item em `steps[]` no callback (a confirmar no spike: como Parallel/Conditional se refletem ali).

## Implicações para o GAMBI

- **QC ≠ Agent:** alvo é `quick_command_slug` (não `agentId`), entrada `input_data` (não `user_prompt`). Adapter async mapearia `model` → `quick_command_slug` no catálogo.
- **Desenho (pós-spike):** novo adapter atrás de `AgentInvokerPort`/`AgentStreamPort` → create-execution + loop de polling com **diff snapshot-a-snapshot** (reusar o `_compute_delta` cumulativo do streamer) → emite `chat.completion.chunk` mapeando steps a thoughts/progresso. Polling adaptativo + keepalive SSE ao VS Code. Vira CAP nova no SPEC antes do código.
- **Spike:** `scripts/spike-quick-commands.sh` (rodar no corp env) captura create-execution + N callbacks durante uma execução real → responde 1-5 acima.
