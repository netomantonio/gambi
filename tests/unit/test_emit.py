"""T2/AC5-6 — emissor do wide event (tiers, formato, robustez)."""

from __future__ import annotations

import json
import logging

from gambi.observability.config import ObservabilityConfig
from gambi.observability.emit import emit
from gambi.observability.wide_event import WideEvent


def _event(**kw) -> WideEvent:
    return WideEvent(request_id="r1", **kw)


def test_metadata_only_by_default(caplog):
    cfg = ObservabilityConfig()  # sem corpos, console
    ev = _event(model="m", upstream_status=502, upstream_error_body="corpo secreto do upstream")
    with caplog.at_level(logging.INFO, logger="gambi.events"):
        emit(ev, cfg)
    msg = caplog.records[-1].getMessage()
    assert "model=m" in msg
    assert "upstream_status=502" in msg
    assert "corpo secreto do upstream" not in msg  # corpo não vaza por default


def test_bodies_flag_includes_truncated_redacted(caplog):
    cfg = ObservabilityConfig(log_bodies=True, max_body=20)
    ev = _event(upstream_error_body='{"client_secret":"shhh"} ' + ("x" * 100))
    with caplog.at_level(logging.INFO, logger="gambi.events"):
        emit(ev, cfg)
    msg = caplog.records[-1].getMessage()
    assert "shhh" not in msg  # redacted
    assert "truncado" in msg  # truncado


def test_raw_includes_bodies_uncut(caplog):
    cfg = ObservabilityConfig(log_raw=True)
    ev = _event(upstream_error_body="X" * 5000)
    with caplog.at_level(logging.INFO, logger="gambi.events"):
        emit(ev, cfg)
    assert "X" * 5000 in caplog.records[-1].getMessage()


def test_json_format_is_parseable(caplog):
    cfg = ObservabilityConfig(log_format="json")
    ev = _event(model="m", outcome="success", http_status=200, n_tools=3)
    with caplog.at_level(logging.INFO, logger="gambi.events"):
        emit(ev, cfg)
    obj = json.loads(caplog.records[-1].getMessage())
    assert obj["model"] == "m"
    assert obj["outcome"] == "success"
    assert obj["n_tools"] == 3


def test_emit_never_raises_on_bad_input():
    # Observabilidade nunca pode derrubar a request.
    emit(None, ObservabilityConfig())  # type: ignore[arg-type]
