# Upload de arquivos para contexto

Permite anexar arquivos a uma chamada de agent via `upload_ids`. Fluxo de 3 passos (form pré-assinado S3).

Fonte: [Upload Files to Contextualize Your Agent Requests](https://ai.stackspot.com/docs/agents/agent-api/upload-files)

## Passo 1 — obter formulário de upload

```
POST https://data-integration-api.stackspot.com/v2/file-upload/form
Content-Type: application/json
Authorization: Bearer <JWT>
x-account-id: <account_id>
```

Body:

```json
{
  "file_name": "documento.pdf",
  "target_type": "CONTEXT",
  "expiration": 60
}
```

Resposta (S3 pré-assinado):

```json
{
  "id": "01JFAKEIDEXAMPLE",
  "url": "https://s3-upload-url",
  "form": {
    "key": "...",
    "x-amz-algorithm": "AWS4-HMAC-SHA256",
    "x-amz-credential": "...",
    "x-amz-date": "...",
    "x-amz-security-token": "...",
    "policy": "...",
    "x-amz-signature": "..."
  }
}
```

> **PERGUNTA ABERTA:** origem do header `x-account-id`. Onde o GAMBI obtém esse valor (vem do token? config?).

## Passo 2 — enviar o arquivo ao S3 (multipart)

`POST` para a `url` retornada, com todos os campos de `form` + o arquivo, como `multipart/form-data`:

```bash
curl -s "{url_da_resposta}" \
  -F "key={form.key}" \
  -F "x-amz-algorithm={...}" \
  -F "x-amz-credential={...}" \
  -F "x-amz-date={...}" \
  -F "x-amz-security-token={...}" \
  -F "policy={...}" \
  -F "x-amz-signature={...}" \
  -F "file=@/caminho/arquivo.pdf"
```

## Passo 3 — usar `upload_ids` na chamada do agent

```json
{
  "streaming": false,
  "user_prompt": "Analise estes arquivos",
  "stackspot_knowledge": false,
  "upload_ids": ["01JFAKEIDEXAMPLE", "02XFAKEIDEXAMPLE"]
}
```

O `id` retornado no passo 1 é o valor que entra em `upload_ids`.

## Notas

- `target_type: "CONTEXT"` para contexto efêmero da chamada (vs `KNOWLEDGE_SOURCE`, ver [04](04-knowledge-sources-api.md)).
- `expiration` em segundos (exemplo usa 60).
- Tamanho máx. de arquivo: **10 MB** (citado no contexto de Knowledge Sources).

## Implicações para o GAMBI

- Relevante se quisermos suportar entradas multimodais/anexos do protocolo OpenAI (ex: `image_url`, conteúdo de arquivo em `messages`).
- É um fluxo de 3 hops (host distinto do inference-app) → custo de latência; provavelmente fora do MVP.

> **PERGUNTA ABERTA:** tipos de arquivo aceitos para `target_type: CONTEXT` e se imagens são suportadas (relevante p/ multimodal OpenAI).
