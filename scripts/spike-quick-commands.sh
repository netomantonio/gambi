#!/usr/bin/env bash
#
# SPIKE — Remote Quick Commands assíncronos do StackSpot (coleta de evidências p/ o GAMBI).
# Roda em Git Bash / MINGW64 (Windows) ou Linux. Requer: curl + python no PATH.
#
# OBJETIVO: responder as PERGUNTAS ABERTAS de docs/stackspot/05-remote-quick-commands.md:
#   1) Durante RUNNING, os steps[].step_result.answer aparecem PARCIAIS/acumulados? (o coração)
#   2) [CONFIRMADO pelo portal] host = genai-code-buddy-api (create + callback). Spike só re-valida.
#   3) Quais valores de status aparecem? (CREATED/RUNNING/COMPLETED/FAILED?)
#   4) Cadência de polling viável vs rate-limit.
#   5) Como os steps de um QC ORQUESTRADO (Prompt/WebRequest/Conditional/Parallel) aparecem no callback.
#
# COMO USAR:
#   1) Exporte (ou preencha abaixo): REALM, CLIENT_ID, CLIENT_SECRET, QC_SLUG, QC_INPUT.
#      - QC_SLUG = o slug de um Remote Quick Command seu (de preferência MULTI-STEP e que demore
#        alguns segundos — quanto mais longo, mais snapshots RUNNING a gente captura).
#   2) bash scripts/spike-quick-commands.sh
#   3) Me envie: out_qc_timeline.txt (o mais importante) + out_qc_create.json + os out_qc_poll_*.json
#      (principalmente um de status RUNNING e o COMPLETED).
#
# O out_qc_timeline.txt mostra, por poll: tempo decorrido, http, status, % e o ANS_LEN de cada step.
# Se ANS_LEN cresce enquanto status=RUNNING => parcial-por-step CONFIRMADO (a sua observação).

set -uo pipefail

# ============================ PREENCHA AQUI (ou exporte) ============================
REALM="${GAMBI_STACKSPOT_REALM:-}"
CLIENT_ID="${GAMBI_STACKSPOT_CLIENT_ID:-}"
CLIENT_SECRET="${GAMBI_STACKSPOT_CLIENT_SECRET:-}"
QC_SLUG="${QC_SLUG:-agentrix-adk-create}"  # slug do Remote Quick Command (multi-step).
# 'agentrix-adk-create' é um GERADOR: monta agent/skill/prompt e devolve o artefato NA RESPOSTA
# (sem provisionar nada na conta — zero side-effect). Ótimo alvo de spike (multi-step, saída grande).
# Ajuste QC_INPUT ao contrato do SEU QC (aqui: descrição do agente a gerar).
QC_INPUT="${QC_INPUT:-Gere um agente chamado spike-demo que responde perguntas sobre Python, com uma skill de exemplos de codigo e um prompt em portugues.}"
# ===================================================================================

IDM="https://idm.stackspot.com"
# Host CONFIRMADO pelo portal (aba "Como usar" do QC agentrix-adk-create): create + callback no MESMO
# host genai-code-buddy-api. (A doc oficial genérica cita genai-data-integration-api p/ create — o
# portal por-QC é a fonte autoritativa da conta.)
CREATE_HOST="${CREATE_HOST:-https://genai-code-buddy-api.stackspot.com}"
# Callback: genai-code-buddy-api confirmado; demais ficam como fallback do autodetect.
CALLBACK_CANDIDATES=("https://genai-code-buddy-api.stackspot.com" "https://genai-data-integration-api.stackspot.com" "https://data-integration-api.stackspot.com")
POLL_INTERVAL="${POLL_INTERVAL:-3}"        # segundos entre polls (cuidado: 20 req/min no Service Credential)
MAX_POLLS="${MAX_POLLS:-40}"               # ~2 min com intervalo 3s

for v in REALM CLIENT_ID CLIENT_SECRET QC_SLUG; do
  if [ -z "${!v}" ]; then echo "ERRO: preencha/exporte $v."; exit 1; fi
done

# ---------- 0) Token ----------
echo ">> [0] Autenticando..."
TOKEN_JSON="$(curl -s "$IDM/$REALM/oidc/oauth/token" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'grant_type=client_credentials' \
  --data-urlencode "client_id=$CLIENT_ID" \
  --data-urlencode "client_secret=$CLIENT_SECRET")"
JWT="$(printf '%s' "$TOKEN_JSON" | python -c 'import sys,json;print(json.load(sys.stdin).get("access_token",""))' 2>/dev/null)"
if [ -z "$JWT" ]; then echo "ERRO: sem access_token. Resposta crua:"; printf '%s\n' "$TOKEN_JSON"; exit 1; fi
echo "   OK"

# ---------- 1) Criar execução ----------
echo ">> [1] create-execution (slug=$QC_SLUG)..."
CREATE_BODY="$(QC_INPUT="$QC_INPUT" python -c 'import os,json;print(json.dumps({"input_data":os.environ["QC_INPUT"]}))')"
curl -s "$CREATE_HOST/v1/quick-commands/create-execution/$QC_SLUG" \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d "$CREATE_BODY" -w $'\n[HTTP %{http_code}]\n' | tee out_qc_create.json >/dev/null
echo "   resposta crua em out_qc_create.json:"; cat out_qc_create.json

EXEC_ID="$(python - <<'PY' 2>/dev/null
import json,sys,re
raw=open("out_qc_create.json",encoding="utf-8").read()
raw=re.sub(r"\n\[HTTP \d+\]\n?$","",raw).strip()
try:
    d=json.loads(raw)
    print(d["execution_id"] if isinstance(d,dict) else str(d))
except Exception:
    print(raw.strip().strip('"'))
PY
)"
if [ -z "$EXEC_ID" ]; then echo "ERRO: não extraí execution_id (veja out_qc_create.json)."; exit 1; fi
echo "   execution_id=$EXEC_ID"

# ---------- autodetect do host de callback ----------
CALLBACK_HOST="${CALLBACK_HOST:-}"
if [ -z "$CALLBACK_HOST" ]; then
  echo ">> [1.5] Detectando host de callback..."
  for h in "${CALLBACK_CANDIDATES[@]}"; do
    code="$(curl -s -o /dev/null -w '%{http_code}' "$h/v1/quick-commands/callback/$EXEC_ID" -H "Authorization: Bearer $JWT")"
    echo "   $h -> HTTP $code"
    if [ "$code" = "200" ]; then CALLBACK_HOST="$h"; break; fi
  done
  [ -z "$CALLBACK_HOST" ] && CALLBACK_HOST="${CALLBACK_CANDIDATES[0]}"  # nenhum 200 ainda: usa o 1º e segue
fi
echo "   usando CALLBACK_HOST=$CALLBACK_HOST"

# ---------- 2) Polling ----------
: > out_qc_timeline.txt
echo ">> [2] Polling do callback (intervalo=${POLL_INTERVAL}s, máx=${MAX_POLLS})..."
START=$(date +%s)
for i in $(seq -w 1 "$MAX_POLLS"); do
  NOW=$(date +%s); ELAPSED=$((NOW-START))
  FILE="out_qc_poll_${i}.json"
  HTTP="$(curl -s -o "$FILE" -w '%{http_code}' "$CALLBACK_HOST/v1/quick-commands/callback/$EXEC_ID" -H "Authorization: Bearer $JWT")"
  # Resumo compacto (status, %, e ANS_LEN por step — é a prova do parcial)
  SUMMARY="$(ELAPSED="$ELAPSED" HTTP="$HTTP" python - "$FILE" <<'PY' 2>/dev/null
import json,os,sys
elapsed=os.environ.get("ELAPSED"); http=os.environ.get("HTTP")
try: d=json.load(open(sys.argv[1],encoding="utf-8"))
except Exception as e: print(f"t={elapsed}s http={http} (JSON inv: {e})"); raise SystemExit
p=d.get("progress",{}) if isinstance(d,dict) else {}
parts=[f"t={elapsed}s http={http} status={p.get('status')} pct={p.get('execution_percentage')}"]
for s in (d.get("steps") or []):
    sr=s.get("step_result")
    ans=sr.get("answer") if isinstance(sr,dict) else None
    al=len(ans) if isinstance(ans,str) else ("null" if sr is None else "?")
    parts.append(f"step[{s.get('execution_order')}]={s.get('step_name')} st={s.get('status')} ans_len={al}")
print(" | ".join(parts))
PY
)"
  echo "   [$i] $SUMMARY"
  echo "$SUMMARY" >> out_qc_timeline.txt
  STATUS="$(python -c 'import json,sys;d=json.load(open(sys.argv[1],encoding="utf-8"));print((d.get("progress") or {}).get("status",""))' "$FILE" 2>/dev/null)"
  case "$STATUS" in COMPLETED|FAILED|FAILURE|ERROR) echo "   -> terminal ($STATUS)"; break;; esac
  sleep "$POLL_INTERVAL"
done

echo
echo "PRONTO. Me envie:"
echo "  out_qc_timeline.txt   (o principal — veja se ANS_LEN cresce enquanto status=RUNNING)"
echo "  out_qc_create.json    (resposta do create-execution)"
echo "  out_qc_poll_*.json    (esp. um RUNNING e o COMPLETED — pro shape exato dos steps)"
echo
echo "Dica: se só veio 1 poll COMPLETED, rode de novo com um QC mais longo, ou POLL_INTERVAL=1."
