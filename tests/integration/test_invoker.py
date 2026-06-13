import httpx
import pytest
import respx

from gambi.adapters.stackspot.client import StackSpotAgentInvoker
from gambi.domain.models import UpstreamError

CHAT_URL = "https://genai-inference-app.stackspot.com/v1/agent/agent-1/chat"


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
                "tokens": {"user": 3, "enrichment": 2, "output": 5},
            },
        )
    )
    async with httpx.AsyncClient() as client:
        reply = await _invoker(client).invoke("agent-1", "o que é uma API?")

    assert reply.message == "uma API é..."
    assert reply.output_tokens == 5
    # confere que o Bearer foi enviado
    sent = route.calls.last.request
    assert sent.headers["Authorization"] == "Bearer tok"


@respx.mock
async def test_invoke_404_raises_upstream_not_found():
    respx.post(CHAT_URL).mock(return_value=httpx.Response(404, json={}))
    async with httpx.AsyncClient() as client:
        with pytest.raises(UpstreamError) as exc:
            await _invoker(client).invoke("agent-1", "x")
    assert exc.value.status_code == 404


@respx.mock
async def test_invoke_500_raises_upstream():
    respx.post(CHAT_URL).mock(return_value=httpx.Response(500, text="boom"))
    async with httpx.AsyncClient() as client:
        with pytest.raises(UpstreamError):
            await _invoker(client).invoke("agent-1", "x")
