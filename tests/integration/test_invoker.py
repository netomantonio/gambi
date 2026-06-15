import json

import httpx
import pytest
import respx

from gambi.adapters.stackspot.client import StackSpotAgentInvoker
from gambi.domain.models import StackSpotAgentOptions, UpstreamError

CHAT_URL = "https://genai-inference-app.stackspot.com/v1/agent/agent-1/chat"

DEFAULT_OPTS = StackSpotAgentOptions()


class FixedToken:
    async def get_token(self) -> str:
        return "tok"


def _invoker(client: httpx.AsyncClient) -> StackSpotAgentInvoker:
    return StackSpotAgentInvoker(client=client, token_provider=FixedToken())


@respx.mock
async def test_invoke_success_maps_reply():
    route = respx.post(CHAT_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "message": "uma API é...",
                "stop_reason": "stop",
                # shape REAL: user/enrichment null, prompt em `input`, campos extras
                "tokens": {"user": None, "enrichment": None, "input": 42, "output": 5},
                "message_id": "01KV66",
                "agent_info": [],
            },
        )
    )
    async with httpx.AsyncClient() as client:
        reply = await _invoker(client).invoke("agent-1", "o que é uma API?", DEFAULT_OPTS)

    assert reply.message == "uma API é..."
    assert reply.usage.prompt_tokens == 42
    assert reply.usage.completion_tokens == 5
    # confere que o Bearer foi enviado
    sent = route.calls.last.request
    assert sent.headers["Authorization"] == "Bearer tok"


@respx.mock
async def test_invoke_sends_per_agent_options_in_payload():
    route = respx.post(CHAT_URL).mock(
        return_value=httpx.Response(200, json={"message": "ok", "stop_reason": "stop"})
    )
    options = StackSpotAgentOptions(
        stackspot_knowledge=False,
        deep_search_ks=True,
        return_ks_in_response=True,
        knowledge_source_ids=("ks-1", "ks-2"),
        agent_version_number=3,
    )
    async with httpx.AsyncClient() as client:
        await _invoker(client).invoke("agent-1", "oi", options)

    body = json.loads(route.calls.last.request.content)
    assert body["streaming"] is False
    assert body["stackspot_knowledge"] is False
    assert body["deep_search_ks"] is True
    assert body["return_ks_in_response"] is True
    assert body["knowledge_source_ids"] == ["ks-1", "ks-2"]
    assert body["agent_version_number"] == 3


@respx.mock
async def test_invoke_404_raises_upstream_not_found():
    respx.post(CHAT_URL).mock(return_value=httpx.Response(404, json={}))
    async with httpx.AsyncClient() as client:
        with pytest.raises(UpstreamError) as exc:
            await _invoker(client).invoke("agent-1", "x", DEFAULT_OPTS)
    assert exc.value.status_code == 404


@respx.mock
async def test_invoke_500_raises_upstream():
    respx.post(CHAT_URL).mock(return_value=httpx.Response(500, text="boom"))
    async with httpx.AsyncClient() as client:
        with pytest.raises(UpstreamError):
            await _invoker(client).invoke("agent-1", "x", DEFAULT_OPTS)
