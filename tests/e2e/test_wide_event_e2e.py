"""T4/T5 — wide event end-to-end: enriquecimento por camada + diagnóstico do 502 (CAP-6).

O critério central de CAP-6: lendo UM evento, dá pra dizer se a falha é do GAMBI ou do
StackSpot. Aqui o caminho real (client httpx + respx) prova que, num ≥400 do StackSpot, o
evento carrega `upstream_status` real e `outcome="upstream_error"`.
"""

from __future__ import annotations

import json
import logging

import httpx
import respx
from fastapi.testclient import TestClient

from gambi.adapters.catalog.config_catalog import ConfigAgentCatalog
from gambi.adapters.http.app import create_app
from gambi.adapters.stackspot.client import StackSpotAgentInvoker
from gambi.application.use_cases import (
    CreateChatCompletion,
    CreateChatCompletionStream,
    ListModels,
)
from gambi.domain.models import AgentReply, AgentTarget, ModelRoute, StackSpotAgentOptions, Usage
from gambi.observability.config import ObservabilityConfig

CHAT_URL = "https://genai-inference-app.stackspot.com/v1/agent/agent-1/chat"


class _FixedToken:
    async def get_token(self) -> str:
        return "tok"


class _FakeInvoker:
    def __init__(self, reply: AgentReply) -> None:
        self.reply = reply

    async def invoke(self, agent_id, user_prompt, options=None) -> AgentReply:
        return self.reply


def _route(options: StackSpotAgentOptions | None = None) -> ModelRoute:
    target = AgentTarget("agent-1", options=options or StackSpotAgentOptions())
    return ModelRoute("stackspot-dev", {"ask": target, "agent": target})


def _build(invoker, observability: ObservabilityConfig, options=None) -> TestClient:
    catalog = ConfigAgentCatalog([_route(options)])
    app = create_app(
        catalog=catalog,
        list_models=ListModels(catalog),
        create_chat_completion=CreateChatCompletion(catalog, invoker),
        create_chat_completion_stream=CreateChatCompletionStream(catalog, None),
        observability=observability,
    )
    return TestClient(app)


def _events(caplog) -> list[dict]:
    return [json.loads(r.getMessage()) for r in caplog.records if r.name == "gambi.events"]


_TOOL_CALL_JSON = (
    '{"action":"tool_call","content":"",'
    '"tool_calls":[{"name":"createFile","arguments_json":"{\\"path\\":\\"hello.py\\"}"}]}'
)


def test_ask_mode_event_fields(caplog):
    client = _build(
        _FakeInvoker(AgentReply("oi", "stop", usage=Usage(1, 2))),
        ObservabilityConfig(log_format="json"),
    )
    with caplog.at_level(logging.INFO, logger="gambi.events"):
        resp = client.post(
            "/v1/chat/completions",
            json={"model": "stackspot-dev", "messages": [{"role": "user", "content": "oi"}]},
        )
    assert resp.status_code == 200
    ev = _events(caplog)[-1]
    assert ev["mode"] == "ask"
    assert ev["n_tools"] == 0
    assert ev["agent_id"] == "agent-1"
    assert ev["agent_action"] == "final"
    assert ev["outcome"] == "success"
    assert ev["http_status"] == 200


def test_agent_mode_tool_call_event_fields(caplog):
    client = _build(
        _FakeInvoker(AgentReply(_TOOL_CALL_JSON, "stop")),
        ObservabilityConfig(log_format="json"),
        options=StackSpotAgentOptions(structured_output=True),
    )
    with caplog.at_level(logging.INFO, logger="gambi.events"):
        resp = client.post(
            "/v1/chat/completions",
            json={
                "model": "stackspot-dev",
                "messages": [{"role": "user", "content": "crie hello.py"}],
                "tools": [
                    {"type": "function", "function": {"name": "createFile", "parameters": {}}}
                ],
            },
        )
    assert resp.status_code == 200
    ev = _events(caplog)[-1]
    assert ev["mode"] == "agent"
    assert ev["n_tools"] == 1
    assert ev["tool_names"] == ["createFile"]
    assert ev["agent_action"] == "tool_call"
    assert ev["outcome"] == "success"


@respx.mock
def test_upstream_4xx_event_diagnoses_stackspot_not_gambi(caplog):
    # O coração de CAP-6: StackSpot recusa (429 "Credit Limit Reached") → o evento aponta
    # o upstream, não o GAMBI.
    respx.post(CHAT_URL).mock(
        return_value=httpx.Response(429, text='{"message":"Credit Limit Reached"}')
    )
    invoker = StackSpotAgentInvoker(
        client=httpx.AsyncClient(),
        token_provider=_FixedToken(),
        observability=ObservabilityConfig(log_format="json", log_bodies=True),
    )
    client = _build(invoker, ObservabilityConfig(log_format="json", log_bodies=True))
    with caplog.at_level(logging.INFO, logger="gambi.events"):
        resp = client.post(
            "/v1/chat/completions",
            json={"model": "stackspot-dev", "messages": [{"role": "user", "content": "oi"}]},
        )
    assert resp.status_code == 502  # ≥400 não-404 → 502 no envelope OpenAI
    ev = _events(caplog)[-1]
    assert ev["upstream_status"] == 429
    assert ev["outcome"] == "upstream_error"
    assert ev["http_status"] == 502
    assert "Credit Limit Reached" in ev["upstream_error_body"]


@respx.mock
def test_upstream_transport_error_event_has_no_status(caplog):
    respx.post(CHAT_URL).mock(side_effect=httpx.ConnectError("sem rede"))
    invoker = StackSpotAgentInvoker(
        client=httpx.AsyncClient(),
        token_provider=_FixedToken(),
        observability=ObservabilityConfig(log_format="json"),
    )
    client = _build(invoker, ObservabilityConfig(log_format="json"))
    with caplog.at_level(logging.INFO, logger="gambi.events"):
        resp = client.post(
            "/v1/chat/completions",
            json={"model": "stackspot-dev", "messages": [{"role": "user", "content": "oi"}]},
        )
    assert resp.status_code == 502
    ev = _events(caplog)[-1]
    assert ev["outcome"] == "upstream_error"
    assert "upstream_status" not in ev  # None → omitido; falha de transporte, não do StackSpot
