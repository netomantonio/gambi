"""BufferedAgentStreamInvoker — obtém a resposta completa via streaming + acumulação.

Fix do teto de ~120s do StackSpot p/ resposta não-streaming (gateway derruba a conexão).
Streaming mantém a conexão viva; acumulamos os deltas no AgentReply inteiro, idêntico ao
que o use case espera (parseia o structured output normalmente).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from gambi.adapters.stackspot.buffered import BufferedAgentStreamInvoker
from gambi.domain.models import AgentStreamEvent, StackSpotAgentOptions, Usage

OPTS = StackSpotAgentOptions()


class _FakeStreamer:
    def __init__(self, events: list[AgentStreamEvent]) -> None:
        self.events = events
        self.seen: tuple[str, str] | None = None

    async def stream(self, agent_id, user_prompt, options) -> AsyncIterator[AgentStreamEvent]:
        self.seen = (agent_id, user_prompt)
        for event in self.events:
            yield event


async def test_accumulates_deltas_into_full_reply():
    # JSON estruturado partido em deltas → acumula no JSON inteiro p/ o parser do use case.
    streamer = _FakeStreamer(
        [
            AgentStreamEvent(delta='{"action":"tool_call",'),
            AgentStreamEvent(delta='"tool_calls":[{"name":"createFile"}]}'),
            AgentStreamEvent(final=True, stop_reason="stop", usage=Usage(7, 9), sources=("ks-a",)),
        ]
    )
    reply = await BufferedAgentStreamInvoker(streamer).invoke("agent-1", "crie x", OPTS)

    assert reply.message == '{"action":"tool_call","tool_calls":[{"name":"createFile"}]}'
    assert reply.stop_reason == "stop"
    assert reply.usage.prompt_tokens == 7
    assert reply.usage.completion_tokens == 9
    assert reply.sources == ("ks-a",)
    assert streamer.seen == ("agent-1", "crie x")


async def test_empty_stream_yields_empty_message():
    streamer = _FakeStreamer([AgentStreamEvent(final=True, stop_reason="stop")])
    reply = await BufferedAgentStreamInvoker(streamer).invoke("a", "p", OPTS)
    assert reply.message == ""
    assert reply.stop_reason == "stop"
    assert reply.usage.prompt_tokens == 0
