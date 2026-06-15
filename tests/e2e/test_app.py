from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from gambi.adapters.catalog.config_catalog import ConfigAgentCatalog
from gambi.adapters.http.app import create_app
from gambi.application.use_cases import (
    CreateChatCompletion,
    CreateChatCompletionStream,
    ListModels,
)
from gambi.domain.models import AgentReply, AgentStreamEvent, CatalogEntry, UpstreamError, Usage


class FakeInvoker:
    def __init__(self, reply: AgentReply) -> None:
        self.reply = reply
        self.seen: tuple[str, str] | None = None

    async def invoke(self, agent_id: str, user_prompt: str, options=None) -> AgentReply:
        self.seen = (agent_id, user_prompt)
        return self.reply


class FakeStreamer:
    def __init__(self, events: list[AgentStreamEvent]) -> None:
        self.events = events

    async def stream(
        self, agent_id: str, user_prompt: str, options=None
    ) -> AsyncIterator[AgentStreamEvent]:
        for event in self.events:
            yield event


def build_client(
    reply: AgentReply | None = None,
    stream_events: list[AgentStreamEvent] | None = None,
) -> tuple[TestClient, FakeInvoker]:
    catalog = ConfigAgentCatalog([CatalogEntry(model_id="stackspot-dev", agent_id="agent-1")])
    invoker = FakeInvoker(reply or AgentReply(message="oi", stop_reason="stop", usage=Usage(1, 2)))
    streamer = FakeStreamer(
        stream_events
        if stream_events is not None
        else [
            AgentStreamEvent(delta="oi"),
            AgentStreamEvent(delta=" mundo"),
            AgentStreamEvent(final=True, stop_reason="stop", usage=Usage(1, 2)),
        ]
    )
    app = create_app(
        list_models=ListModels(catalog),
        create_chat_completion=CreateChatCompletion(catalog, invoker),
        create_chat_completion_stream=CreateChatCompletionStream(catalog, streamer),
    )
    return TestClient(app), invoker


def test_health():
    client, _ = build_client()
    assert client.get("/health").json() == {"status": "ok"}


def test_list_models_openai_shape():
    client, _ = build_client()
    body = client.get("/v1/models").json()
    assert body["object"] == "list"
    assert body["data"][0]["id"] == "stackspot-dev"
    assert body["data"][0]["object"] == "model"


def test_chat_completion_happy_path():
    client, invoker = build_client(
        AgentReply(
            message="uma API é uma interface",
            stop_reason="stop",
            usage=Usage(4, 6),
        )
    )
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "stackspot-dev",
            "messages": [{"role": "user", "content": "o que é uma API?"}],
            "temperature": 0.9,  # D4: deve ser aceito e ignorado
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["object"] == "chat.completion"
    assert body["model"] == "stackspot-dev"
    assert body["choices"][0]["message"]["content"] == "uma API é uma interface"
    assert body["choices"][0]["finish_reason"] == "stop"
    assert body["usage"]["total_tokens"] == 10
    # o invoker recebeu o agentId resolvido e o prompt achatado
    assert invoker.seen[0] == "agent-1"


def test_chat_completion_with_tools_is_accepted_not_422():
    # Agent mode envia `tools`; não podemos rejeitar (422) — aceitamos e respondemos em texto.
    client, _ = build_client()
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "stackspot-dev",
            "messages": [{"role": "user", "content": "crie um arquivo"}],
            "tools": [{"type": "function", "function": {"name": "create_file", "parameters": {}}}],
            "tool_choice": "auto",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["object"] == "chat.completion"


def test_chat_completion_unknown_model_returns_openai_error():
    client, _ = build_client()
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "inexistente", "messages": [{"role": "user", "content": "oi"}]},
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "model_not_found"
    assert body["error"]["type"] == "invalid_request_error"


def test_chat_completion_streaming_emits_openai_sse():
    client, _ = build_client(
        stream_events=[
            AgentStreamEvent(delta="uma API"),
            AgentStreamEvent(delta=" é uma interface"),
            AgentStreamEvent(final=True, stop_reason="stop", usage=Usage(3, 4)),
        ]
    )
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "stackspot-dev",
            "messages": [{"role": "user", "content": "o que é uma API?"}],
            "stream": True,
        },
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    text = resp.text
    # primeiro delta carrega o role assistant
    assert '"role": "assistant"' in text
    assert "uma API" in text and "é uma interface" in text
    assert '"object": "chat.completion.chunk"' in text
    assert '"finish_reason": "stop"' in text
    assert text.strip().endswith("data: [DONE]")


class _BoomStreamer:
    async def stream(self, agent_id, user_prompt, options=None):
        raise UpstreamError("StackSpot retornou 401", status_code=401)
        yield  # pragma: no cover — torna isto um async generator


def test_streaming_upstream_error_is_surfaced_not_silent():
    # Erro após o 200 não pode falhar em silêncio: vira conteúdo visível + [DONE].
    catalog = ConfigAgentCatalog([CatalogEntry(model_id="stackspot-dev", agent_id="agent-1")])
    app = create_app(
        list_models=ListModels(catalog),
        create_chat_completion=CreateChatCompletion(catalog, FakeInvoker(AgentReply("x", "stop"))),
        create_chat_completion_stream=CreateChatCompletionStream(catalog, _BoomStreamer()),
    )
    client = TestClient(app)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "stackspot-dev",
            "messages": [{"role": "user", "content": "oi"}],
            "stream": True,
        },
    )
    assert resp.status_code == 200
    assert "[GAMBI erro:" in resp.text
    assert "401" in resp.text
    assert resp.text.strip().endswith("data: [DONE]")


def test_streaming_unknown_model_returns_error_before_stream():
    client, _ = build_client()
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "inexistente",
            "messages": [{"role": "user", "content": "oi"}],
            "stream": True,
        },
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "model_not_found"
