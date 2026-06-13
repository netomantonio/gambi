# Remote Quick Commands — execução assíncrona

Modelo **alternativo** ao Agents API: dispara uma execução e faz **polling** pelo resultado. Assíncrono (não streaming). Provavelmente não é o caminho do MVP do GAMBI, mas é o único onde a doc publica limites de rate.

Fonte: [Create and Execute Remote Quick Commands](https://ai.stackspot.com/docs/quick-commands/create-remote-qc)

## 1. Criar execução

```
POST https://genai-data-integration-api.stackspot.com/v1/quick-commands/create-execution/{quick_command_slug}
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

Resposta: retorna um `execution_id`.

## 2. Polling de status/resultado

```
GET https://data-integration-api.stackspot.com/v1/quick-commands/callback/{execution_id}
Authorization: Bearer <access_token>
```

Retorna status da execução, percentual de progresso, tempos e o resultado final.

> **PERGUNTA ABERTA:** valores possíveis de status, shape exato do resultado final, e intervalo de polling recomendado.

## Retry e limites (documentados aqui)

- **Retry automático:** até 3 tentativas adicionais (4 no total) por passo de LLM.
- **Service Credential:** 20 requests/min, 6.000/dia.
- **Personal Access Token:** 100 requests / 24h.

> Estes são os **únicos limites de rate publicados na doc**, no contexto de Quick Commands. **PERGUNTA ABERTA:** se valem também para a Agents API síncrona ([02](02-agents-api.md)). O GAMBI deve, por segurança, assumir limites parecidos e implementar backpressure/429 até confirmar.

## Implicações para o GAMBI

- Modelo **assíncrono com polling** não casa bem com `chat/completions` (síncrono/streaming). Preferir a Agents API ([02](02-agents-api.md)) para o caminho OpenAI.
- Poderia mapear a um modo "batch"/job se o GAMBI vier a expor algo além do chat — fora do escopo inicial.
- A principal informação aproveitável aqui são os **limites de rate** e o comportamento de **retry**.
