"""Configuração via ambiente. Sem dependência extra.

Variáveis:
  GAMBI_STACKSPOT_REALM          realm = SLUG DA CONTA no IDM (copiado do portal "Access Token";
                                 NÃO é o literal 'stackspot'). Obrigatório para auth real.
  GAMBI_STACKSPOT_CLIENT_ID      client id da Service Credential / PAT
  GAMBI_STACKSPOT_CLIENT_SECRET  client secret/key
  GAMBI_STACKSPOT_KNOWLEDGE      default de stackspot_knowledge p/ agents sem flag (true/false)

Catálogo de agents (uma das duas formas):
  GAMBI_AGENTS_FILE   caminho p/ um JSON com agents + opções por agent (preferível). Cada item:
                      {model_id, agent_id, stackspot_knowledge?, deep_search_ks?,
                       return_ks_in_response?, knowledge_source_ids?, agent_version_number?}
  GAMBI_AGENTS        atalho "modelo=agentId,modelo2=agentId2" (sem flags por agent).
                      Usado se GAMBI_AGENTS_FILE não estiver setado/existente.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from gambi.domain.models import CatalogEntry, StackSpotAgentOptions


@dataclass
class Settings:
    realm: str
    client_id: str
    client_secret: str
    agents: list[CatalogEntry] = field(default_factory=list)

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        env = env if env is not None else dict(os.environ)
        default_knowledge = env.get("GAMBI_STACKSPOT_KNOWLEDGE", "true").lower() != "false"

        agents_file = env.get("GAMBI_AGENTS_FILE", "").strip()
        if agents_file and Path(agents_file).is_file():
            agents = load_agents_file(Path(agents_file), default_knowledge)
        else:
            agents = parse_agents(env.get("GAMBI_AGENTS", ""), default_knowledge)

        return cls(
            # Sem default enganoso: realm é o slug da conta, varia por conta (OQ-5).
            realm=env.get("GAMBI_STACKSPOT_REALM", ""),
            client_id=env.get("GAMBI_STACKSPOT_CLIENT_ID", ""),
            client_secret=env.get("GAMBI_STACKSPOT_CLIENT_SECRET", ""),
            agents=agents,
        )


def parse_agents(raw: str, default_knowledge: bool) -> list[CatalogEntry]:
    """Parse de 'modelo=agentId,modelo2=agentId2' (atalho simples, sem flags por agent)."""
    entries: list[CatalogEntry] = []
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        model_id, agent_id = (part.strip() for part in pair.split("=", 1))
        if model_id and agent_id:
            entries.append(
                CatalogEntry(
                    model_id=model_id,
                    agent_id=agent_id,
                    options=StackSpotAgentOptions(stackspot_knowledge=default_knowledge),
                )
            )
    return entries


def load_agents_file(path: Path, default_knowledge: bool) -> list[CatalogEntry]:
    """Carrega o catálogo de um JSON (lista de objetos com model_id/agent_id + flags por agent)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    entries: list[CatalogEntry] = []
    for item in data:
        options = StackSpotAgentOptions(
            stackspot_knowledge=bool(item.get("stackspot_knowledge", default_knowledge)),
            deep_search_ks=bool(item.get("deep_search_ks", False)),
            return_ks_in_response=bool(item.get("return_ks_in_response", False)),
            knowledge_source_ids=tuple(item.get("knowledge_source_ids") or ()),
            agent_version_number=item.get("agent_version_number"),
        )
        entries.append(
            CatalogEntry(
                model_id=str(item["model_id"]),
                agent_id=str(item["agent_id"]),
                options=options,
            )
        )
    return entries
