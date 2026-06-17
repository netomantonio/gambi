# Conectar o GAMBI ao VS Code Copilot Chat

Guia para usar o GAMBI como **provider de modelos** no VS Code Copilot Chat — os agents do StackSpot aparecem como modelos selecionáveis, no molde de um Ollama local. **Sem assinatura do GitHub Copilot e sem login** (validado na doc do VS Code; ver Risco 1 do brief).

> ✅ **Confirmado por pesquisa (2026-06-13, código-fonte do `vscode-copilot-chat`):** o provider "Custom Endpoint" já está no **VS Code estável** (v1.120+). Ele **não chama `GET /v1/models`** — você declara o modelo na config com a **URL completa** do endpoint de chat. Espera **SSE OpenAI-padrão**. Detalhes em `docs/stackspot/08-gaps-pesquisa.md`.

## Pré-requisitos
- GAMBI rodando (ver `README.md`): `uv run uvicorn gambi.main:app` com `GAMBI_AGENTS` apontando para os agents.
- **VS Code ≥ 1.120** (onde o provider "Custom Endpoint" estabilizou) + extensão **GitHub Copilot Chat** atualizada. ⚠️ Confirmado: **1.117 NÃO tem** "Custom Endpoint" no menu — só OpenAI/OpenRouter/etc. Se não aparecer a opção, **atualize o VS Code** (e a extensão; considere a pre-release). Ref.: microsoft/vscode#317939.

## Passos
1. No VS Code, abra a paleta de comandos e rode **`Chat: Manage Language Models`**.
2. Escolha **Add Models** → **Custom Endpoint** (provider _OpenAI Compatible_).
3. Configure o modelo:
   - **URL (completa):** `http://localhost:8000/v1/chat/completions` — o VS Code faz POST **exatamente** nesta URL (não anexa nada).
   - **API type:** **Chat Completions**.
   - **id / name:** use um dos `model_id` do seu `GAMBI_AGENTS` (ex: `stackspot-dev`).
   - **API key:** qualquer valor não-vazio (o GAMBI não valida a key do cliente; ele autentica no StackSpot com as próprias credenciais).
4. No Copilot Chat, selecione o modelo do GAMBI e converse.

A configuração persiste em `chatLanguageModels.json`. O editor **não** consulta `/v1/models` (você declara o modelo aqui); o GAMBI mantém `/v1/models` mesmo assim, para outros clientes OpenAI.

## Suporte a streaming
O GAMBI implementa **streaming SSE no formato OpenAI** (`stream:true`), que é o modo que o Copilot Chat usa. O consumo do streaming do StackSpot é **defensivo** (auto-detecta o formato) porque o shape do SSE do StackSpot não é público — **valide no ambiente corporativo** (ver `docs/stackspot/08-gaps-pesquisa.md`, OQ-1). Se o StackSpot não fizer streaming real, o GAMBI degrada para uma resposta única re-emitida como stream.

## Ask mode vs Agent mode

- **Ask mode** (chat normal): ✅ funciona. O agent responde markdown; você aplica com "Apply"/copiar.
- **Agent mode** (Copilot edita/cria arquivos): ⚙️ **suportado, experimental** — o GAMBI traduz tool calling
  do VS Code (`tools` → prompt; resposta estruturada do agent → `tool_calls`). **Requer um agent dedicado
  com Structured Output + system prompt** configurados conforme **[stackspot-agent-mode-setup.md](stackspot-agent-mode-setup.md)**.
  Ainda **pendente de validação real** (OQ-7: como o JSON estruturado volta na API).

**Config:**
- Modelo de **chat** (agent comum): `toolCalling: false`.
- Modelo de **agent mode** (agent estruturado): `toolCalling: true` — declare-o como um modelo separado
  apontando para o mesmo GAMBI, com o `id` do agent estruturado.

Se o agent estruturado ainda não estiver pronto, o GAMBI **degrada com segurança**: resposta não-JSON
vira texto normal (não quebra), apenas sem edição autônoma de arquivos.

## Limitações do v1
- Agent mode é **experimental** até validar o Structured Output contra a API real (OQ-7).
- Sem code completions inline (exigem conta GitHub — fora do escopo).
- Multimodal/anexos fora do v1.

## Troubleshooting (armadilhas reais já enfrentadas)

**Não aparece "Custom Endpoint" no menu Add Models (só OpenAI/Anthropic/Gemini/OpenRouter/Ollama).**
→ VS Code antigo demais. O provider estabilizou na **≥ 1.120**; **1.117 não tem**. Atualize o VS Code (e a extensão GitHub Copilot Chat; considere a pre-release). Sem essa opção, **não há como** apontar o Copilot Chat pro GAMBI. Ref.: microsoft/vscode#317939.

**Você seleciona "OpenAI" e nada funciona / aparece `Error fetching available OpenRouter models`.**
→ Provider errado. O **"OpenAI"** fala com `api.openai.com` (só pede API key, **sem campo de URL**) e ignora qualquer URL custom → nunca chama o localhost. O erro do **OpenRouter** é de OUTRO provider (refresh de catálogo) — ruído, pode remover. Use **"Custom Endpoint"** (pede **URL + model id**). Regra: se a tela só pede API key → provider errado; se pede **URL** → certo.

**`net::ERR_TUNNEL_CONNECTION_FAILED`.**
→ Proxy corporativo: o VS Code (Chromium) está mandando a chamada de `localhost` pelo proxy. Adicione no settings.json: `"http.noProxy": ["localhost", "127.0.0.1", "::1"]`, recarregue a janela e re-adicione o modelo. (O `curl` funciona porque tem bypass próprio; o VS Code usa o proxy dele.)

**Teste definitivo de que está no provider certo:** ao mandar mensagem no chat, o **log do GAMBI** mostra `POST /v1/chat/completions`. Se não chega request nenhuma no log → você ainda está no provider errado (ou sem a opção Custom Endpoint).
