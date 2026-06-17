"""T1/AC1 — contexto request-scoped do wide event."""

from __future__ import annotations

from gambi.observability import (
    WideEvent,
    bind_event,
    enrich,
    get_current_event,
    reset_event,
)


def test_enrich_without_context_is_noop():
    # Sem evento ligado, enrich não levanta e não cria evento (caminho não-HTTP / unit).
    assert get_current_event() is None
    enrich(model="x", n_tools=3)
    assert get_current_event() is None


def test_enrich_accumulates_on_bound_event():
    ev = WideEvent(request_id="r1")
    token = bind_event(ev)
    try:
        enrich(model="m", n_tools=3)
        enrich(upstream_status=502)
        cur = get_current_event()
        assert cur is ev
        assert ev.model == "m"
        assert ev.n_tools == 3
        assert ev.upstream_status == 502
    finally:
        reset_event(token)
    assert get_current_event() is None


def test_new_event_binds_and_sets_request_id():
    from gambi.observability import new_event

    ev, token = new_event(method="POST", path="/v1/chat/completions")
    try:
        assert ev.method == "POST"
        assert ev.path == "/v1/chat/completions"
        assert ev.request_id  # uuid gerado
        assert get_current_event() is ev
    finally:
        reset_event(token)
