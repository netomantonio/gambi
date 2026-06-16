"""Configuração via ambiente. Sem dependência extra.

Variáveis:
  GAMBI_STACKSPOT_REALM          realm = SLUG DA CONTA no IDM (copiado do portal "Access Token";
                                 NÃO é o literal 'stackspot'). Obrigatório para auth real.
  GAMBI_STACKSPOT_CLIENT_ID      client id da Service Credential / PAT
  GAMBI_STACKSPOT_CLIENT_SECRET  client secret/key
  GAMBI_STACKSPOT_KNOWLEDGE      default de stackspot_knowledge p/ agents sem flag (true/false)

Catálogo de modelos (uma das duas formas):
  GAMBI_AGENTS_FILE   caminho p/ um JSON. Cada item é um modelo exportado, em uma de duas formas:
                      - simples (mode-agnostic): {model_id, agent_id, <flags por agent>}
                      - alias por modo: {model_id, modes: {ask: {agent_id, <flags>},
                                                            agent: {agent_id, <flags>}}}
                        ("agent" cobre edit+agent = modo com tools; "ask" = sem tools)
                      flags por agent: stackspot_knowledge?, deep_search_ks?,
                                       return_ks_in_response?, knowledge_source_ids?,
                                       agent_version_number?, structured_output?
  GAMBI_AGENTS        atalho "modelo=agentId,modelo2=agentId2" (simples, sem flags).
                      Usado se GAMBI_AGENTS_FILE não estiver setado/existente.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from gambi.domain.models import AgentTarget, ModelRoute, StackSpotAgentOptions


@dataclass
class Settings:
    realm: str
    client_id: str
    client_secret: str
    agents: list[ModelRoute] = field(default_factory=list)

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


def _options_from(spec: dict, default_knowledge: bool) -> StackSpotAgentOptions:
    return StackSpotAgentOptions(
        stackspot_knowledge=bool(spec.get("stackspot_knowledge", default_knowledge)),
        deep_search_ks=bool(spec.get("deep_search_ks", False)),
        return_ks_in_response=bool(spec.get("return_ks_in_response", False)),
        knowledge_source_ids=tuple(spec.get("knowledge_source_ids") or ()),
        agent_version_number=spec.get("agent_version_number"),
        structured_output=bool(spec.get("structured_output", False)),
    )


def _simple_route(model_id: str, agent_id: str, options: StackSpotAgentOptions) -> ModelRoute:
    """Modelo mode-agnostic: mesmo target para ask e agent."""
    target = AgentTarget(agent_id=agent_id, options=options)
    return ModelRoute(model_id=model_id, by_mode={"ask": target, "agent": target})


def parse_agents(raw: str, default_knowledge: bool) -> list[ModelRoute]:
    """Parse de 'modelo=agentId,modelo2=agentId2' (atalho simples, sem flags por agent)."""
    routes: list[ModelRoute] = []
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        model_id, agent_id = (part.strip() for part in pair.split("=", 1))
        if model_id and agent_id:
            routes.append(
                _simple_route(
                    model_id, agent_id, StackSpotAgentOptions(stackspot_knowledge=default_knowledge)
                )
            )
    return routes


def load_agents_file(path: Path, default_knowledge: bool) -> list[ModelRoute]:
    """Carrega o catálogo de um JSON. Cada item é simples (model_id+agent_id) ou alias (modes)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    routes: list[ModelRoute] = []
    for item in data:
        model_id = str(item["model_id"])
        modes = item.get("modes")
        if isinstance(modes, dict) and modes:
            by_mode = {
                mode: AgentTarget(
                    agent_id=str(spec["agent_id"]), options=_options_from(spec, default_knowledge)
                )
                for mode, spec in modes.items()
                if isinstance(spec, dict) and spec.get("agent_id")
            }
            if by_mode:
                routes.append(ModelRoute(model_id=model_id, by_mode=by_mode))
                continue
        routes.append(
            _simple_route(model_id, str(item["agent_id"]), _options_from(item, default_knowledge))
        )
    return routes
