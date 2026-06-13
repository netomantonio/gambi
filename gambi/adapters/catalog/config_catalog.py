"""ConfigAgentCatalog (D7) — catálogo de agents vindo de configuração.

Impl. inicial enquanto OQ-3 (existe API de listagem de agents?) não é resolvida.
Trocável por uma impl. baseada em API sem tocar a aplicação (mesma porta).
"""

from __future__ import annotations

from gambi.domain.models import CatalogEntry


class ConfigAgentCatalog:
    """Implementa AgentCatalogPort a partir de uma lista estática de entradas."""

    def __init__(self, entries: list[CatalogEntry]) -> None:
        # dedup por model_id mantendo a primeira ocorrência; índice para resolução O(1).
        self._by_model: dict[str, CatalogEntry] = {}
        for entry in entries:
            self._by_model.setdefault(entry.model_id, entry)

    def list_models(self) -> list[CatalogEntry]:
        return list(self._by_model.values())

    def resolve(self, model_id: str) -> str | None:
        entry = self._by_model.get(model_id)
        return entry.agent_id if entry else None
