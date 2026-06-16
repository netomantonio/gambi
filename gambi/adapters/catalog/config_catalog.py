"""ConfigAgentCatalog (D7) — catálogo de modelos vindo de configuração.

Cada `ModelRoute` é um modelo exportado (`model_id`) que roteia para um agent StackSpot por modo
de chat (ask vs agent). `resolve(model_id, mode)` devolve o alvo já achatado em `CatalogEntry`.
Trocável por uma impl. baseada em API sem tocar a aplicação (mesma porta).
"""

from __future__ import annotations

from gambi.domain.models import CatalogEntry, ModelRoute


class ConfigAgentCatalog:
    """Implementa AgentCatalogPort a partir de uma lista estática de ModelRoutes."""

    def __init__(self, routes: list[ModelRoute]) -> None:
        # dedup por model_id mantendo a primeira ocorrência; índice para resolução O(1).
        self._by_model: dict[str, ModelRoute] = {}
        for route in routes:
            self._by_model.setdefault(route.model_id, route)

    def list_models(self) -> list[CatalogEntry]:
        # Uma entrada por model_id exportado (só o model_id importa para /v1/models).
        return [
            CatalogEntry(
                model_id=r.model_id,
                agent_id=r.target_for("agent").agent_id,
                options=r.target_for("agent").options,
            )
            for r in self._by_model.values()
        ]

    def resolve(self, model_id: str, mode: str) -> CatalogEntry | None:
        route = self._by_model.get(model_id)
        if route is None:
            return None
        target = route.target_for(mode)
        return CatalogEntry(model_id=model_id, agent_id=target.agent_id, options=target.options)
