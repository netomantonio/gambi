"""WideEvent + contexto request-scoped (CAP-6 / AD-1).

Um único evento estruturado por request. Criado na borda HTTP, enriquecido por camada
(route, use case, StackSpot adapter) via `ContextVar`. O domínio NÃO importa este módulo.

`enrich()` é no-op quando não há evento ligado ao contexto — assim caminhos não-HTTP
(testes de unidade, chamadas diretas) não quebram nem emitem nada.
"""

from __future__ import annotations

import contextvars
import uuid
from dataclasses import dataclass, field

# Campos do catálogo (ver observability-wide-events.md). Todos opcionais: cada camada
# preenche o que conhece. `tool_names` usa default_factory (lista mutável).


@dataclass
class WideEvent:
    request_id: str
    # HTTP middleware
    method: str | None = None
    path: str | None = None
    http_status: int | None = None
    duration_ms: float | None = None
    # HTTP route
    model: str | None = None
    mode: str | None = None
    stream: bool | None = None
    n_messages: int | None = None
    n_tools: int | None = None
    n_tool_results: int | None = None
    tool_names: list[str] = field(default_factory=list)
    # application / use case
    agent_id: str | None = None
    agent_action: str | None = None  # final | tool_call | unmatched
    schema_repairs: int | None = None
    # StackSpot adapter
    prompt_chars: int | None = None
    upstream_url: str | None = None
    upstream_status: int | None = None
    upstream_latency_ms: float | None = None
    # desfecho
    outcome: str | None = None  # success | upstream_error | ... | internal_error
    error_type: str | None = None
    error_detail: str | None = None  # detalhe da exceção (ex.: classe+msg do erro de transporte)
    # corpos (só coletados sob flag — privacidade em camadas)
    upstream_request_body: str | None = None
    upstream_error_body: str | None = None


_current: contextvars.ContextVar[WideEvent | None] = contextvars.ContextVar(
    "gambi_wide_event", default=None
)


def bind_event(event: WideEvent) -> contextvars.Token:
    """Liga um evento ao contexto atual. Retorna um token p/ reset."""
    return _current.set(event)


def reset_event(token: contextvars.Token) -> None:
    _current.reset(token)


def new_event(
    *, method: str | None = None, path: str | None = None, request_id: str | None = None
) -> tuple[WideEvent, contextvars.Token]:
    """Cria + liga um evento novo. Retorna (evento, token)."""
    event = WideEvent(request_id=request_id or uuid.uuid4().hex, method=method, path=path)
    token = bind_event(event)
    return event, token


def get_current_event() -> WideEvent | None:
    return _current.get()


def enrich(**fields: object) -> None:
    """Acumula campos no evento atual. No-op silencioso se não houver evento ligado."""
    event = _current.get()
    if event is None:
        return
    for key, value in fields.items():
        setattr(event, key, value)
