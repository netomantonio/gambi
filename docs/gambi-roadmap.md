# GAMBI — Visão, Arquitetura de Add-ons e Roadmap

> Documento vivo. Consolida as ideias validadas nas conversas de design. Não é o contrato v1
> (esse é o `_bmad-output/planning-artifacts/specs/spec-gambi/SPEC.md`); aqui mora a direção e o
> backlog de capacidades. Pela disciplina SDD, cada capacidade vira item no SPEC antes de virar código.

## 1. A tese (por que o GAMBI existe)

O GAMBI é a **camada inteligente que dá ao StackSpot capacidade não-nativa** para funcionar como provider
de LLM no VS Code (vscode-lm/Copilot Chat), incluindo agent mode. Se o StackSpot oferecesse tudo isso
nativamente, o GAMBI não precisaria existir — logo, "remar contra a corrente" é a **função**, não um defeito.

Dois princípios que mudam o nível de exigência:
- **O bar é "útil", não "perfeito".** Até o agent mode nativo (GPT/Claude) erra tool call, entra em loop, chama
  ferramenta errada — e as pessoas usam porque é líquido positivo. O GAMBI precisa ser net-positive, não impecável.
- **O GAMBI pode ADICIONAR robustez que o modelo cru não tem:** validar/reparar/repetir o structured output,
  aterrar (RAG) os argumentos de tool call no código real, citar fontes. Estar **no meio do loop** é uma vantagem.

## 2. Princípio de arquitetura: núcleo fino + add-ons opt-in

- **Núcleo (default):** só o que o VS Code manda. Proxy stateless, drop-in, zero fricção. É a promessa
  original ("aponta o Custom Endpoint e funciona"). **Sagrado: nenhum add-on pode pesar ou quebrar este caminho.**
- **Add-ons (opt-in):** escalam poder progressivamente, desligáveis, sem onerar quem só quer o básico.
- **Regra de ouro:** usabilidade básica intacta sempre; poder é escolha de quem quer.

## 3. Tiers de capacidade (a escada de poder)

| Tier | O que é | Estado do GAMBI |
|---|---|---|
| **0 — Núcleo** | Chat + agent mode usando só o contexto que o VS Code envia | Proxy stateless (é o que existe hoje) |
| **1 — RAG leve (add-on)** | Indexa o que o VS Code já manda (arquivos abertos, `#file`, anexos) numa KS efêmera → grounding básico | Proxy + indexação oportunista |
| **2 — Serviço local + filesystem (add-on)** | Roda em background com acesso ao workspace; indexa o codebase inteiro em KS (`.zip` + `SYNTACTIC`), auto-sync no save, branch-aware | Serviço stateful local |
| **3 — Bidirecional (CLI + MCP)** | CLI p/ setup/indexação/admin; servidor MCP que expõe poderes do GAMBI como ferramentas nativas ao editor | Plataforma |

## 4. GAMBI como serviço + CLI + MCP (as três superfícies)

- **Serviço background:** o proxy sempre-on (+ indexador nos tiers altos). É o coração.
- **CLI:** setup, indexação, admin (provisionar/sincronizar KS, status, limpar) — para o caminho local/fs.
- **MCP server:** expõe capacidades do GAMBI como **ferramentas nativas** ao agent do VS Code.

> **Nuance importante sobre MCP (não confundir as superfícies):**
> - Como **model provider**, o agent StackSpot (via GAMBI) só usa ferramentas se **emitir `tool_calls`** —
>   ou seja, ainda depende do structured output (a aposta da OQ-7). MCP **não** remove isso para esse caminho.
> - Como **MCP server**, o GAMBI fornece a **implementação** de ferramentas (ex.: "buscar no codebase via
>   KS do StackSpot") que **qualquer modelo** no editor — inclusive um nativo (GPT/Claude) — chama nativamente.
>   Esse caminho é **independente do structured output** e, portanto, mais robusto para *prover* poder.
> Conclusão: as duas superfícies são complementares. MCP dá um caminho robusto de **entregar conhecimento/retrieval
> do StackSpot a qualquer modelo**, sem depender da fragilidade do tool-calling emulado.

## 5. Backlog de capacidades (das conversas de design)

| # | Ideia | Ganho | Tier | Esforço |
|---|------|-------|------|---------|
| A | KS por workspace + auto-sync (zip inicial, re-upload incremental no save) | Agent conhece o repo | 2 | Médio-alto |
| B | Split `SYNTACTIC` + 1 KS por repo (ou por camada domínio/adapters) | Retrieval de código preciso | 1-2 | Baixo |
| C | `knowledge_source_ids` por request → roteamento de grounding | "pergunta sobre módulo X → KS de X" | 1 | Baixo |
| D | Injetar arquivo atual + diagnostics antes da tool call | Tool-calling aterrado (mais confiável) | 1-2 | Médio |
| E | Agents especializados + KS como "modelos" (`codebase-expert`, `arch-advisor`) | Variedade útil no `/v1/models` | 0-1 | Baixo |
| F | `return_ks_in_response` → citações no editor | Confiança/rastreabilidade | 0 | Baixo | ✅ feito |
| G | Repair/retry/validação do structured output no GAMBI | Robustez do agent mode | 0 | Médio | ✅ feito |
| H | KS por branch/worktree | Grounding no que se está mexendo | 2 | Médio |
| I | Indexar `docs/`, ADRs, SPEC/arquitetura | Agent respeita as convenções do time | 1-2 | Baixo |
| J | GAMBI como MCP server (retrieval do codebase como tool nativa) | Poder a qualquer modelo, sem depender de structured output | 3 | Alto |

## 6. Mecânica confirmada da API de KS (base para A/B/C)
- Criar: `POST data-integration-api.stackspot.com/v1/knowledge-sources` (`slug`/`name`/`type` ∈ api|snippet|custom).
- Popular: **só via file-upload** (form→S3→`/file-upload/{id}/knowledge-objects` com `split_strategy`). `custom` aceita `.zip` → bulk index num upload.
- Split `SYNTACTIC` (code-aware) p/ snippet/custom.
- Incremental: sem PATCH → **deletar (por id / `?standalone` / arquivos) e reenviar**.
- Associação: KS no agent **+ `knowledge_source_ids` por request**.

## 7. Restrições e perguntas abertas (honestidade)
- **Segredos/privacidade:** NUNCA indexar `.env`/`.git`/segredos; respeitar `.gitignore`. Crítico (player financeiro).
- **Sem PATCH de KO** → sync incremental exige mapear arquivo→KO ids (listar objetos) p/ deletar+reenviar deltas.
- **10MB/arquivo**; rate/quota de KS **não documentados** → repo grande pode esbarrar (zip ajuda).
- **Provisionar KS exige escopo `ai_dev`/`ai_admin`** (Service Credential), mais que o chat.
- **`standalone` KO (add manual sem arquivo):** citado no delete, mas endpoint de *adicionar* não documentado → PERGUNTA ABERTA (simplificaria o sync por-chunk).
- **Acesso a filesystem (tier 2):** é a bifurcação central — exige GAMBI local/serviço, não proxy remoto.
- **OQ-7 (structured output) ainda pendente** de validação real — base do agent mode.

## 8. Sequência recomendada
1. **Carimbar o núcleo (tier 0):** validar chat + agent mode no editor real (streaming + structured output / OQ-7).
2. **Add-ons leves (tier 1):** B, C, F, I — baixo esforço, valor rápido, sem fs.
3. **Spike de indexação (tier 2):** zip → upload → `SYNTACTIC` → anexar → pergunta grounded → medir `enrichment`.
4. **MCP/CLI (tier 3):** quando o serviço local existir.

Cada passo: capacidade no SPEC antes do código (SDD). Add-ons sempre desligáveis, núcleo intocado.
