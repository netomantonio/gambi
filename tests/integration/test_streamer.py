"""Testes do StackSpotAgentStreamer contra o formato SSE real: frames `data: {<objeto>}`.

Cobre cumulativo, incremental e o fallback de JSON único — sem depender do content-type.
"""

import httpx
import pytest
import respx

from gambi.adapters.stackspot.stream import StackSpotAgentStreamer
from gambi.domain.models import StackSpotAgentOptions, UpstreamError
from gambi.observability.config import ObservabilityConfig
from gambi.observability.wide_event import WideEvent, bind_event, reset_event

CHAT_URL = "https://genai-inference-app.stackspot.com/v1/agent/agent-1/chat"

DEFAULT_OPTS = StackSpotAgentOptions()


class FixedToken:
    async def get_token(self) -> str:
        return "tok"


async def _collect(body: bytes, content_type: str = "text/event-stream"):
    respx.post(CHAT_URL).mock(
        return_value=httpx.Response(200, headers={"content-type": content_type}, content=body)
    )
    async with httpx.AsyncClient() as client:
        streamer = StackSpotAgentStreamer(client=client, token_provider=FixedToken())
        deltas, finals = [], []
        async for ev in streamer.stream("agent-1", "x", DEFAULT_OPTS):
            if ev.delta:
                deltas.append(ev.delta)
            if ev.final:
                finals.append(ev)
    return deltas, finals


@respx.mock
async def test_sse_cumulative_message_emits_only_new_suffix():
    # Cada frame traz o `message` ACUMULADO (mesmo objeto da resposta não-stream).
    body = (
        b'data: {"message": "a", "stop_reason": null}\n\n'
        b'data: {"message": "ab", "stop_reason": null}\n\n'
        b'data: {"message": "abc", "stop_reason": "stop", "tokens": {"input": 5, "output": 3}}\n\n'
    )
    deltas, finals = await _collect(body)
    assert "".join(deltas) == "abc"  # reconstrói o texto sem duplicar
    assert finals[-1].stop_reason == "stop"
    assert finals[-1].usage.prompt_tokens == 5
    assert finals[-1].usage.completion_tokens == 3


@respx.mock
async def test_sse_incremental_message_passes_through():
    body = (
        b'data: {"message": "1"}\n\n'
        b'data: {"message": "\\n2"}\n\n'
        b'data: {"message": "\\n3", "stop_reason": "stop"}\n\n'
    )
    deltas, finals = await _collect(body)
    assert "".join(deltas) == "1\n2\n3"
    assert finals[-1].stop_reason == "stop"


@respx.mock
async def test_single_json_fallback_when_no_frames():
    # Caso sem streaming: corpo é um JSON único (shape real com tokens null/input).
    body = (
        b'{"message": "resposta inteira", "stop_reason": "stop", '
        b'"tokens": {"user": null, "enrichment": null, "input": 6331, "output": 2970}}'
    )
    deltas, finals = await _collect(body, content_type="application/json")
    assert "".join(deltas) == "resposta inteira"
    assert finals[-1].usage.prompt_tokens == 6331
    assert finals[-1].usage.completion_tokens == 2970


@respx.mock
async def test_sse_with_done_terminator():
    body = b'data: {"message": "oi", "stop_reason": "stop"}\n\ndata: [DONE]\n\n'
    deltas, finals = await _collect(body)
    assert "".join(deltas) == "oi"


@respx.mock
async def test_sse_captures_sources_in_final_event():
    body = b'data: {"message": "oi", "stop_reason": "stop", "knowledge_source_id": ["ks-a"]}\n\n'
    _, finals = await _collect(body)
    assert finals[-1].sources == ("ks-a",)


@respx.mock
async def test_stream_enriches_wide_event_on_upstream_error():
    # CAP-6 no caminho streaming: ≥400 enriquece upstream_status + body (sob flag).
    respx.post(CHAT_URL).mock(return_value=httpx.Response(429, text="Credit Limit Reached"))
    event = WideEvent(request_id="r1")
    token = bind_event(event)
    try:
        async with httpx.AsyncClient() as client:
            streamer = StackSpotAgentStreamer(
                client=client,
                token_provider=FixedToken(),
                observability=ObservabilityConfig(log_bodies=True),
            )
            with pytest.raises(UpstreamError):
                async for _ in streamer.stream("agent-1", "ola", DEFAULT_OPTS):
                    pass
    finally:
        reset_event(token)
    assert event.upstream_status == 429
    assert event.upstream_error_body and "Credit Limit Reached" in event.upstream_error_body
    assert event.prompt_chars == len("ola")


@respx.mock
async def test_stream_enriches_error_detail_on_transport_disconnect():
    # O caso real do 502 agêntico: gateway derruba a conexão → RemoteProtocolError, sem status.
    respx.post(CHAT_URL).mock(
        side_effect=httpx.RemoteProtocolError("Server disconnected without sending a response.")
    )
    event = WideEvent(request_id="r1")
    token = bind_event(event)
    try:
        async with httpx.AsyncClient() as client:
            streamer = StackSpotAgentStreamer(client=client, token_provider=FixedToken())
            with pytest.raises(UpstreamError):
                async for _ in streamer.stream("agent-1", "x", DEFAULT_OPTS):
                    pass
    finally:
        reset_event(token)
    assert event.upstream_status is None
    assert event.error_detail and "RemoteProtocolError" in event.error_detail
