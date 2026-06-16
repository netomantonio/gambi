#!/usr/bin/env bash
#
# Validação do agent ESTRUTURADO do StackSpot (agent mode) — coleta de evidências para o GAMBI.
# Roda em Git Bash / MINGW64 (Windows) ou Linux. Requer: curl + python no PATH.
#
# COMO USAR:
#   1) Preencha as 4 variáveis abaixo (ou exporte como variáveis de ambiente antes de rodar).
#      - AGENT_ID = o id do agent que tem Structured Output + system prompt configurados
#        (ver docs/stackspot-agent-mode-setup.md). NÃO é o agent de chat comum.
#   2) bash scripts/validar-agent-mode.sh
#   3) Me envie os arquivos gerados: out_0_token_meta.txt, out_1_toolcall_nonstream.txt,
#      out_2_toolcall_stream.txt, out_3_final_nonstream.txt
#
# O QUE CADA SAÍDA DEVE MOSTRAR (é isso que eu preciso confirmar):
#   out_1: o `message` deve ser um JSON com  "action":"tool_call"  e um createFile em "tool_calls".
#          >>> ESTE É O TESTE PRINCIPAL (a pendência "A2"): provar que o agent DECIDE chamar a ferramenta.
#   out_2: a MESMA chamada com streaming=true — pra ver como o JSON chega (fragmentado em frames `data:`?).
#   out_3: a mesma situação MAS com resultado da ferramenta já dado → deve vir "action":"final".
#   out_0: metadados do token (expires_in, token_type, scope) — sem o access_token. Fecha a dúvida do TTL.

set -uo pipefail

# ============================ PREENCHA AQUI ============================
REALM="${GAMBI_STACKSPOT_REALM:-}"            # slug da conta (portal "Access Token")
CLIENT_ID="${GAMBI_STACKSPOT_CLIENT_ID:-}"
CLIENT_SECRET="${GAMBI_STACKSPOT_CLIENT_SECRET:-}"
AGENT_ID="${GAMBI_AGENT_ID:-}"                # id do AGENT ESTRUTURADO
# ======================================================================

IDM="https://idm.stackspot.com"
INFER="https://genai-inference-app.stackspot.com"

for v in REALM CLIENT_ID CLIENT_SECRET AGENT_ID; do
  if [ -z "${!v}" ]; then echo "ERRO: preencha a variável $v no topo do script (ou exporte no ambiente)."; exit 1; fi
done

# ---------- 0) Token ----------
echo ">> [0/3] Autenticando e capturando metadados do token..."
TOKEN_JSON="$(curl -s "$IDM/$REALM/oidc/oauth/token" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'grant_type=client_credentials' \
  --data-urlencode "client_id=$CLIENT_ID" \
  --data-urlencode "client_secret=$CLIENT_SECRET")"

JWT="$(printf '%s' "$TOKEN_JSON" | python -c 'import sys,json;print(json.load(sys.stdin).get("access_token",""))' 2>/dev/null)"
if [ -z "$JWT" ]; then echo "ERRO: não obtive access_token. Resposta crua:"; printf '%s\n' "$TOKEN_JSON"; exit 1; fi

# metadados SEM o access_token (seguro de compartilhar)
printf '%s' "$TOKEN_JSON" | python -c 'import sys,json;d=json.load(sys.stdin);print(json.dumps({k:v for k,v in d.items() if k!="access_token"}, indent=2, ensure_ascii=False))' > out_0_token_meta.txt
echo "   OK (token obtido; metadados em out_0_token_meta.txt)"

# ---------- prompts (o que o GAMBI injetaria) ----------
# Teste principal: SÓ ferramentas + conversa, SEM resultados → o agent deve decidir chamar a ferramenta.
read -r -d '' PROMPT_TOOLCALL <<'EOF' || true
## FERRAMENTAS DISPONÍVEIS
- nome: createFile
  descrição: Cria um arquivo novo com o conteúdo dado.
  argumentos: {"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}
- nome: runInTerminal
  descrição: Executa um comando no terminal.
  argumentos: {"type":"object","properties":{"command":{"type":"string"}},"required":["command"]}

## CONVERSA
[Usuário] crie um arquivo hello.py que imprime olá
EOF

# Contraste: o resultado da ferramenta já foi dado → o agent deve FINALIZAR.
read -r -d '' PROMPT_FINAL <<'EOF' || true
## FERRAMENTAS DISPONÍVEIS
- nome: createFile
  descrição: Cria um arquivo novo com o conteúdo dado.
  argumentos: {"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}

## CONVERSA
[Usuário] crie um arquivo hello.py que imprime olá

## RESULTADOS DAS FERRAMENTAS
- name: createFile
  result: arquivo hello.py criado com sucesso
EOF

# ---------- helper: monta o body JSON (escapando o prompt com python) e chama o agent ----------
chamar () {  # args: <nome_saida> <prompt> <streaming true|false>
  local nome="$1" prompt="$2" streaming="$3" body
  body="$(PROMPT="$prompt" ST="$streaming" python -c 'import os,json;print(json.dumps({"streaming":os.environ["ST"]=="true","user_prompt":os.environ["PROMPT"],"stackspot_knowledge":False,"return_ks_in_response":True}))')"
  echo ">> $nome (streaming=$streaming) -> out_${nome}.txt"
  curl -sN "$INFER/v1/agent/$AGENT_ID/chat" \
    -H "Authorization: Bearer $JWT" \
    -H "Content-Type: application/json" \
    -d "$body" | tee "out_${nome}.txt"
  echo; echo "----------------------------------------------------------------"
}

echo ">> [1/3] TESTE PRINCIPAL — tool_call (sem RESULTADOS, não-streaming)"
chamar "1_toolcall_nonstream" "$PROMPT_TOOLCALL" false

echo ">> [2/3] tool_call em STREAMING (mesmo input)"
chamar "2_toolcall_stream" "$PROMPT_TOOLCALL" true

echo ">> [3/3] contraste — final (com RESULTADOS, não-streaming)"
chamar "3_final_nonstream" "$PROMPT_FINAL" false

echo
echo "PRONTO. Me envie estes arquivos:"
echo "  out_0_token_meta.txt  out_1_toolcall_nonstream.txt  out_2_toolcall_stream.txt  out_3_final_nonstream.txt"
echo
echo "Confira rápido no out_1: o campo \"message\" deve conter  \"action\":\"tool_call\"  e \"createFile\"."
