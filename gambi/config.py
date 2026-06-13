"""Configuração via ambiente. Sem dependência extra — lê os.environ.

Variáveis:
  GAMBI_STACKSPOT_REALM          realm = SLUG DA CONTA no IDM (copiado do portal "Access Token";
                                 NÃO é o literal 'stackspot'). Obrigatório para auth real.
  GAMBI_STACKSPOT_CLIENT_ID      client id da Service Credential / PAT
  GAMBI_STACKSPOT_CLIENT_SECRET  client secret/key
  GAMBI_AGENTS                   catálogo "modelo=agentId" separado por vírgula
                                 ex: "stackspot-dev=01ABC...,stackspot-arch=01XYZ..."
  GAMBI_STACKSPOT_KNOWLEDGE      "true"/"false" — usar Knowledge Sources (default true)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from gambi.domain.models import CatalogEntry


@dataclass
class Settings:
    realm: str
    client_id: str
    client_secret: str
    agents: list[CatalogEntry] = field(default_factory=list)
    stackspot_knowledge: bool = True

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        env = env if env is not None else dict(os.environ)
        return cls(
            # Sem default enganoso: realm é o slug da conta, varia por conta (OQ-5).
            realm=env.get("GAMBI_STACKSPOT_REALM", ""),
            client_id=env.get("GAMBI_STACKSPOT_CLIENT_ID", ""),
            client_secret=env.get("GAMBI_STACKSPOT_CLIENT_SECRET", ""),
            agents=parse_agents(env.get("GAMBI_AGENTS", "")),
            stackspot_knowledge=env.get("GAMBI_STACKSPOT_KNOWLEDGE", "true").lower() != "false",
        )


def parse_agents(raw: str) -> list[CatalogEntry]:
    """Faz parse de 'modelo=agentId,modelo2=agentId2' em entradas de catálogo."""
    entries: list[CatalogEntry] = []
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        model_id, agent_id = pair.split("=", 1)
        model_id, agent_id = model_id.strip(), agent_id.strip()
        if model_id and agent_id:
            entries.append(CatalogEntry(model_id=model_id, agent_id=agent_id))
    return entries
