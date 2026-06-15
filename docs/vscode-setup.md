# Conectar o GAMBI ao VS Code Copilot Chat

Guia para usar o GAMBI como **provider de modelos** no VS Code Copilot Chat — os agents do StackSpot aparecem como modelos selecionáveis, no molde de um Ollama local. **Sem assinatura do GitHub Copilot e sem login** (validado na doc do VS Code; ver Risco 1 do brief).

> ✅ **Confirmado por pesquisa (2026-06-13, código-fonte do `vscode-copilot-chat`):** o provider "Custom Endpoint" já está no **VS Code estável** (v1.120+). Ele **não chama `GET /v1/models`** — você declara o modelo na config com a **URL completa** do endpoint de chat. Espera **SSE OpenAI-padrão**. Detalhes em `docs/stackspot/08-gaps-pesquisa.md`.

## Pré-requisitos
- GAMBI rodando (ver `README.md`): `uv run uvicorn gambi.main:app` com `GAMBI_AGENTS` apontando para os agents.
- VS Code (Insiders, enquanto o Custom Endpoint não chega ao estável).

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

## Ask mode vs Agent mode (importante)

- **Ask mode** (chat normal): ✅ funciona. O agent responde markdown com blocos de código; você aplica com "Apply"/copiar.
- **Agent mode** (Copilot edita/cria arquivos sozinho): ⚠️ **não funciona como autônomo** com o GAMBI hoje. O agent mode depende de **tool calling** (o editor manda `tools` e espera `tool_calls`), e o **StackSpot não expõe tool calling** via API — os toolkits dele são internos ao agent. O GAMBI aceita o request (não dá erro) e o agent responde em **texto**, mas o editor **não consegue editar/criar arquivos automaticamente**.

**Recomendação de config:** ao declarar o modelo no `chatLanguageModels.json`, marque **`toolCalling: false`** (e `vision: false`). Assim o VS Code usa o modelo em ask mode e não tenta o fluxo de agent mode (que ficaria travado esperando `tool_calls`).

**Como confirmar empiricamente:** com o GAMBI rodando (logs ligados), tente o agent mode uma vez e olhe o console — o GAMBI loga `agent mode detectado: N tools (...)`. Isso prova que o editor está pedindo tool calling que o StackSpot não atende.

## Limitações do v1
- **Agent mode autônomo** (editar/criar arquivos via tools) — depende de tool calling, que o StackSpot não expõe.
- Sem code completions inline (exigem conta GitHub — fora do escopo).
- Multimodal/anexos fora do v1.
