"""Observabilidade do GAMBI — wide events (CAP-6). Infra cross-cutting, fora do domínio."""

from __future__ import annotations

from gambi.observability.wide_event import (
    WideEvent,
    bind_event,
    enrich,
    get_current_event,
    new_event,
    reset_event,
)

__all__ = [
    "WideEvent",
    "bind_event",
    "reset_event",
    "new_event",
    "get_current_event",
    "enrich",
]
