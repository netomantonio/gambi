from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from gambi.adapters.catalog.config_catalog import ConfigAgentCatalog
from gambi.adapters.http.app import create_app
from gambi.application.use_cases import (
    CreateChatCompletion,
    CreateChatCompletionStream,
    ListModels,
)
from gambi.domain.models import (
    AgentReply,
    AgentStreamEvent,
    AgentTarget,
    ModelRoute,
    StackSpotAgentOptions,
    UpstreamError,
    Usage,
)


def _route(model_id="stackspot-dev", agent_id="agent-1", options=None) -> ModelRoute:
    """Rota mode-agnostic p/ testes: mesmo target em ask e agent."""
    target = AgentTarget(agent_id=agent_id, options=options or StackSpotAgentOptions())
    return ModelRoute(model_id=model_id, by_mode={"ask": target, "agent": target})


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
    catalog = ConfigAgentCatalog([_route()])
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
        catalog=catalog,
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


def test_agent_mode_prompt_format_reaches_stackspot():
    # Com tools no request, o GAMBI deve montar o user_prompt no contrato de agent mode.
    client, invoker = build_client()
    client.post(
        "/v1/chat/completions",
        json={
            "model": "stackspot-dev",
            "messages": [{"role": "user", "content": "crie hello.py"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "createFile",
                        "description": "Cria um arquivo",
                        "parameters": {"type": "object"},
                    },
                }
            ],
        },
    )
    prompt = invoker.seen[1]
    assert "## FERRAMENTAS DISPONÍVEIS" in prompt
    assert "createFile" in prompt
    assert "## CONVERSA" in prompt
    assert "crie hello.py" in prompt


_TOOL_CALL_JSON = (
    '{"action":"tool_call","content":"",'
    '"tool_calls":[{"name":"createFile","arguments_json":"{\\"path\\":\\"hello.py\\"}"}]}'
)


def test_agent_mode_tool_call_nonstream_renders_openai_tool_calls():
    client, _ = build_client(AgentReply(message=_TOOL_CALL_JSON, stop_reason="stop"))
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "stackspot-dev",
            "messages": [{"role": "user", "content": "crie hello.py"}],
            "tools": [{"type": "function", "function": {"name": "createFile", "parameters": {}}}],
        },
    )
    assert resp.status_code == 200
    choice = resp.json()["choices"][0]
    assert choice["finish_reason"] == "tool_calls"
    assert choice["message"]["content"] is None
    tc = choice["message"]["tool_calls"][0]
    assert tc["type"] == "function"
    assert tc["function"]["name"] == "createFile"
    assert tc["function"]["arguments"] == '{"path":"hello.py"}'


def test_agent_mode_tool_call_streaming_emits_tool_calls_sse():
    client, _ = build_client(AgentReply(message=_TOOL_CALL_JSON, stop_reason="stop"))
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "stackspot-dev",
            "messages": [{"role": "user", "content": "crie hello.py"}],
            "tools": [{"type": "function", "function": {"name": "createFile", "parameters": {}}}],
            "stream": True,
        },
    )
    assert resp.status_code == 200
    text = resp.text
    assert '"tool_calls"' in text
    assert "createFile" in text
    assert '"finish_reason": "tool_calls"' in text
    assert text.strip().endswith("data: [DONE]")


class _SequenceInvoker:
    """Invoker que devolve uma resposta diferente por chamada (p/ testar repair retry)."""

    def __init__(self, replies: list[AgentReply]) -> None:
        self._replies = replies
        self.calls = 0

    async def invoke(self, agent_id: str, user_prompt: str, options=None) -> AgentReply:
        reply = self._replies[min(self.calls, len(self._replies) - 1)]
        self.calls += 1
        return reply


def _app_with_invoker(invoker) -> TestClient:
    catalog = ConfigAgentCatalog([_route()])
    app = create_app(
        catalog=catalog,
        list_models=ListModels(catalog),
        create_chat_completion=CreateChatCompletion(catalog, invoker),
        create_chat_completion_stream=CreateChatCompletionStream(catalog, FakeStreamer([])),
    )
    return TestClient(app)


def _agent_post(client: TestClient):
    return client.post(
        "/v1/chat/completions",
        json={
            "model": "stackspot-dev",
            "messages": [{"role": "user", "content": "crie hello.py"}],
            "tools": [{"type": "function", "function": {"name": "createFile", "parameters": {}}}],
        },
    )


def test_agent_mode_repair_retry_recovers_tool_call():
    invoker = _SequenceInvoker(
        [
            AgentReply(message="desculpe, segue a resposta", stop_reason="stop"),  # fora do schema
            AgentReply(message=_TOOL_CALL_JSON, stop_reason="stop"),  # válido após repair
        ]
    )
    resp = _agent_post(_app_with_invoker(invoker))
    assert resp.status_code == 200
    assert invoker.calls == 2  # houve um repair retry
    assert resp.json()["choices"][0]["finish_reason"] == "tool_calls"


def test_agent_mode_repair_gives_up_after_one_retry():
    invoker = _SequenceInvoker(
        [
            AgentReply(message="texto 1", stop_reason="stop"),
            AgentReply(message="texto 2", stop_reason="stop"),
            AgentReply(message="texto 3", stop_reason="stop"),  # não deve ser alcançado (cap=1)
        ]
    )
    resp = _agent_post(_app_with_invoker(invoker))
    assert resp.status_code == 200
    assert invoker.calls == 2  # 1 original + 1 repair, depois desiste
    body = resp.json()
    assert body["choices"][0]["finish_reason"] == "stop"
    assert body["choices"][0]["message"]["content"] == "texto 2"  # fallback p/ o texto


def _app_with_ks_agent(invoker=None, streamer=None) -> TestClient:
    catalog = ConfigAgentCatalog(
        [_route(options=StackSpotAgentOptions(return_ks_in_response=True))]
    )
    app = create_app(
        catalog=catalog,
        list_models=ListModels(catalog),
        create_chat_completion=CreateChatCompletion(
            catalog, invoker or FakeInvoker(AgentReply("x", "stop"))
        ),
        create_chat_completion_stream=CreateChatCompletionStream(
            catalog, streamer or FakeStreamer([])
        ),
    )
    return TestClient(app)


def test_chat_appends_sources_footer_when_return_ks_on():
    invoker = FakeInvoker(
        AgentReply(message="resposta", stop_reason="stop", sources=("ks-a", "ks-b"))
    )
    resp = _app_with_ks_agent(invoker=invoker).post(
        "/v1/chat/completions",
        json={"model": "stackspot-dev", "messages": [{"role": "user", "content": "oi"}]},
    )
    content = resp.json()["choices"][0]["message"]["content"]
    assert content.startswith("resposta")
    assert "Fontes:" in content and "ks-a" in content and "ks-b" in content


def test_chat_no_footer_when_flag_off():
    # build_client usa um agent SEM return_ks_in_response → sem rodapé, mesmo com sources.
    client, _ = build_client(AgentReply(message="resposta", stop_reason="stop", sources=("ks-a",)))
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "stackspot-dev", "messages": [{"role": "user", "content": "oi"}]},
    )
    assert "Fontes:" not in resp.json()["choices"][0]["message"]["content"]


def test_streaming_appends_sources_footer_when_return_ks_on():
    streamer = FakeStreamer(
        [
            AgentStreamEvent(delta="oi"),
            AgentStreamEvent(final=True, stop_reason="stop", sources=("ks-a",)),
        ]
    )
    resp = _app_with_ks_agent(streamer=streamer).post(
        "/v1/chat/completions",
        json={
            "model": "stackspot-dev",
            "messages": [{"role": "user", "content": "oi"}],
            "stream": True,
        },
    )
    assert "Fontes:" in resp.text and "ks-a" in resp.text
    assert resp.text.strip().endswith("data: [DONE]")


_FINAL_JSON = '{"action":"final","content":"olá do agent","tool_calls":[]}'


def _app_with_structured_agent(invoker, return_ks=False) -> TestClient:
    catalog = ConfigAgentCatalog(
        [
            _route(
                options=StackSpotAgentOptions(
                    structured_output=True, return_ks_in_response=return_ks
                )
            )
        ]
    )
    app = create_app(
        catalog=catalog,
        list_models=ListModels(catalog),
        create_chat_completion=CreateChatCompletion(catalog, invoker),
        create_chat_completion_stream=CreateChatCompletionStream(catalog, FakeStreamer([])),
    )
    return TestClient(app)


def test_structured_agent_ask_mode_nonstream_unwraps_content():
    # Sem tools, mas agent estruturado → parseia e devolve content limpo (não vaza JSON).
    client = _app_with_structured_agent(FakeInvoker(AgentReply(_FINAL_JSON, "stop")))
    body = client.post(
        "/v1/chat/completions",
        json={"model": "stackspot-dev", "messages": [{"role": "user", "content": "oi"}]},
    ).json()
    content = body["choices"][0]["message"]["content"]
    assert content == "olá do agent"
    assert "action" not in content  # JSON do schema não vazou


def test_structured_agent_ask_mode_streaming_unwraps_content():
    client = _app_with_structured_agent(FakeInvoker(AgentReply(_FINAL_JSON, "stop")))
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "stackspot-dev",
            "messages": [{"role": "user", "content": "oi"}],
            "stream": True,
        },
    )
    text = resp.text
    assert "olá do agent" in text
    assert '"action"' not in text  # nada de fragmento de JSON cru
    assert '"object": "chat.completion.chunk"' in text
    assert text.strip().endswith("data: [DONE]")


def test_structured_agent_final_gets_sources_footer():
    invoker = FakeInvoker(AgentReply(_FINAL_JSON, "stop", sources=("ks-a",)))
    body = (
        _app_with_structured_agent(invoker, return_ks=True)
        .post(
            "/v1/chat/completions",
            json={"model": "stackspot-dev", "messages": [{"role": "user", "content": "oi"}]},
        )
        .json()
    )
    content = body["choices"][0]["message"]["content"]
    assert content.startswith("olá do agent")
    assert "Fontes:" in content and "ks-a" in content


def test_alias_routes_to_different_agent_per_mode_and_exports_one_model():
    invoker = FakeInvoker(AgentReply("ok", "stop"))
    route = ModelRoute(
        model_id="stackspot-llm-5.1",
        by_mode={
            "ask": AgentTarget("agent-ask"),
            "agent": AgentTarget("agent-tools", StackSpotAgentOptions(structured_output=True)),
        },
    )
    catalog = ConfigAgentCatalog([route])
    app = create_app(
        catalog=catalog,
        list_models=ListModels(catalog),
        create_chat_completion=CreateChatCompletion(catalog, invoker),
        create_chat_completion_stream=CreateChatCompletionStream(catalog, FakeStreamer([])),
    )
    client = TestClient(app)

    # /v1/models exporta só o alias, não os agents internos
    ids = [m["id"] for m in client.get("/v1/models").json()["data"]]
    assert ids == ["stackspot-llm-5.1"]

    # ask (sem tools) → agent do ask
    client.post(
        "/v1/chat/completions",
        json={"model": "stackspot-llm-5.1", "messages": [{"role": "user", "content": "oi"}]},
    )
    assert invoker.seen[0] == "agent-ask"

    # agent (com tools) → agent estruturado
    client.post(
        "/v1/chat/completions",
        json={
            "model": "stackspot-llm-5.1",
            "messages": [{"role": "user", "content": "crie x"}],
            "tools": [{"type": "function", "function": {"name": "createFile", "parameters": {}}}],
        },
    )
    assert invoker.seen[0] == "agent-tools"


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
    catalog = ConfigAgentCatalog([_route()])
    app = create_app(
        catalog=catalog,
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
