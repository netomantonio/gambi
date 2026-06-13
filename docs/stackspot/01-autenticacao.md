# Autenticação — StackSpot AI

Toda chamada às APIs do StackSpot usa um **Bearer token** JWT obtido via OAuth 2.0 *client credentials*.

## Endpoint de token

```
POST https://idm.stackspot.com/{realm}/oidc/oauth/token
Content-Type: application/x-www-form-urlencoded
```

Body (form-urlencoded):

| Campo | Valor |
|---|---|
| `grant_type` | `client_credentials` |
| `client_id` | seu client id |
| `client_secret` | seu client secret/key |

Exemplo (extraindo o token com `jq`):

```bash
export JWT=$(curl -s "https://idm.stackspot.com/$REALM/oidc/oauth/token" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=client_credentials' \
  -d "client_id=$CLIENT_ID" \
  -d "client_secret=$CLIENT_KEY" \
  | jq -r '.access_token')
```

A resposta é um JSON contendo pelo menos `access_token`.

> **PERGUNTA ABERTA:** demais campos da resposta de token (`expires_in`, `token_type`, `refresh_token`?) não foram confirmados na doc. O GAMBI precisa saber o TTL para fazer cache/refresh do token — confirmar `expires_in`.

## `realm`

- **Freemium / exemplos da doc:** usam o realm literal `stackspot` → `https://idm.stackspot.com/stackspot/oidc/oauth/token`.
- **Enterprise:** usam `{{your_account_realm}}` (placeholder), indicando que cada conta tem um realm próprio.

> **PERGUNTA ABERTA:** como o GAMBI descobre o `realm` correto da conta-alvo? Provavelmente vira variável de configuração/segredo. Confirmar se Freemium é sempre `stackspot`.

## Tipos de credencial

| Tipo | Como obter | Limites conhecidos |
|---|---|---|
| **Personal Access Token (PAT)** | Portal StackSpot AI → avatar → *My Profile* → seção *Access Token* → *Generate Client Key*. Usado em contas Freemium. | 100 requests / 24h (limite citado p/ Quick Commands) |
| **Service Credential** | Conta Enterprise; requer permissões `ai_dev` e `ai_admin`. | 20 requests/min, 6.000/dia (limite citado p/ Quick Commands) |

> **PERGUNTA ABERTA:** os limites acima foram documentados no contexto de **Quick Commands**. Não está confirmado se a Agents API síncrona (`/v1/agent/.../chat`) tem os mesmos limites. Ver [05-remote-quick-commands.md](05-remote-quick-commands.md).

## Uso do token

Em todas as APIs de execução/gestão:

```
Authorization: Bearer <access_token>
```

## Implicações para o GAMBI

- O proxy gerencia **suas próprias** credenciais StackSpot (client_id/secret via env/segredo). O cliente OpenAI manda uma `Authorization: Bearer sk-...` que o GAMBI **não repassa** — ele autentica separadamente no StackSpot.
- O GAMBI deve **cachear o token** e renovar antes de expirar (depende de `expires_in` — pergunta aberta).
- Decisão de design em aberto: o GAMBI suporta múltiplos tenants (vários client_id) ou um conjunto fixo de credenciais? Isso afeta como a `api_key` do cliente OpenAI é interpretada.
