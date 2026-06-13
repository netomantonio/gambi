# Knowledge Sources via API

Gestão de Knowledge Sources (KS) — fontes de conhecimento associáveis a agents. Provavelmente **fora do caminho crítico do GAMBI** (o proxy consome agents já configurados), mas documentado para completude.

Fonte: [Create, update, and delete KS via API](https://ai.stackspot.com/docs/knowledge-source/create-update-via-api)

## Host e auth

```
https://data-integration-api.stackspot.com
Authorization: Bearer <JWT>
Content-Type: application/json
```

## Criar Knowledge Source

```
POST /v1/knowledge-sources
```

```json
{
  "slug": "my-cli-ks-v2",
  "name": "my-cli-ks-v2",
  "description": "KS created via CLI",
  "type": "api|snippet|custom"
}
```

## Subir arquivos para uma KS

**Passo 1 — form de upload:**

```
POST /v2/file-upload/form
```

```json
{
  "file_name": "<filename>",
  "target_id": "<KS slug>",
  "target_type": "KNOWLEDGE_SOURCE",
  "expiration": 600
}
```

(o upload em si segue o mesmo padrão multipart S3 do [03-upload-files.md](03-upload-files.md))

**Passo 2 — converter em knowledge objects:**

```
POST /v1/file-upload/{upload_id}/knowledge-objects
```

```json
{
  "split_strategy": "NONE|LINES_QUANTITY|TOKENS_QUANTITY|CHARACTERS_QUANTITY|SYNTACTIC|ENDPOINT",
  "split_quantity": 500,
  "split_overlap": 50
}
```

## Listar knowledge objects

```
GET /v1/knowledge-sources/<KS slug>/objects
```

## Deletar

| Operação | Endpoint |
|---|---|
| Por ID | `DELETE /v1/knowledge-sources/<KS slug>/objects/<ko id>` |
| Todos os objetos | `DELETE /v1/knowledge-sources/<KS slug>/objects` |
| Só standalone | `DELETE /v1/knowledge-sources/<KS slug>/objects?standalone=true` |
| Só de arquivos enviados | `DELETE /v1/knowledge-sources/<KS slug>/objects?standalone=false` |

## Notas

- Tamanho máx. por arquivo: **10 MB**.

## Implicações para o GAMBI

- Não faz parte da tradução OpenAI↔StackSpot do chat. Manter como referência; só vira escopo se o GAMBI precisar provisionar KS programaticamente (improvável no MVP).
