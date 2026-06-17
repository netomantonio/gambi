"""T3/AC2 — middleware ASGI emite 1 evento por request; emit nunca derruba a request."""

from __future__ import annotations

import json
import logging

from fastapi.testclient import TestClient

from gambi.adapters.catalog.config_catalog import ConfigAgentCatalog
from gambi.adapters.http.app import create_app
from gambi.application.use_cases import (
    CreateChatCompletion,
    CreateChatCompletionStream,
    ListModels,
)
from gambi.domain.models import AgentReply, AgentTarget, ModelRoute, Usage
from gambi.observability.config import ObservabilityConfig


class _FakeInvoker:
    async def invoke(self, agent_id, user_prompt, options=None) -> AgentReply:
        return AgentReply(message="oi", stop_reason="stop", usage=Usage(1, 2))


def _client(observability: ObservabilityConfig | None = None) -> TestClient:
    target = AgentTarget("agent-1")
    catalog = ConfigAgentCatalog([ModelRoute("stackspot-dev", {"ask": target, "agent": target})])
    app = create_app(
        catalog=catalog,
        list_models=ListModels(catalog),
        create_chat_completion=CreateChatCompletion(catalog, _FakeInvoker()),
        create_chat_completion_stream=CreateChatCompletionStream(catalog, None),
        observability=observability or ObservabilityConfig(log_format="json"),
    )
    return TestClient(app)


def _events(caplog) -> list[dict]:
    return [json.loads(rec.getMessage()) for rec in caplog.records if rec.name == "gambi.events"]


def test_health_emits_exactly_one_event(caplog):
    with caplog.at_level(logging.INFO, logger="gambi.events"):
        resp = _client().get("/health")
    assert resp.status_code == 200
    events = _events(caplog)
    assert len(events) == 1
    ev = events[0]
    assert ev["method"] == "GET"
    assert ev["path"] == "/health"
    assert ev["http_status"] == 200
    assert ev["outcome"] == "success"
    assert ev["request_id"]
    assert "duration_ms" in ev


def test_emit_failure_does_not_crash_request(monkeypatch):
    import gambi.adapters.http.middleware as mw

    def boom(*_args, **_kwargs):
        raise RuntimeError("emit explodiu")

    monkeypatch.setattr(mw, "emit", boom)
    resp = _client().get("/health")
    assert resp.status_code == 200  # observabilidade quebrada não derruba a request
