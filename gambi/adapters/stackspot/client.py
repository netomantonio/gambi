"""StackSpotAgentInvoker — implementa AgentInvokerPort via httpx.

Endpoint: POST {inference_base_url}/v1/agent/{agentId}/chat
Ver docs/stackspot/02-agents-api.md.
"""

from __future__ import annotations

import httpx

from gambi.adapters.stackspot.request_payload import build_payload
from gambi.adapters.stackspot.schemas_stackspot import StackSpotChatResponse
from gambi.adapters.stackspot.tokens import usage_from_tokens
from gambi.application.ports import TokenProviderPort
from gambi.domain.models import AgentReply, StackSpotAgentOptions, UpstreamError

_DEFAULT_INFERENCE_URL = "https://genai-inference-app.stackspot.com"


class StackSpotAgentInvoker:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        token_provider: TokenProviderPort,
        inference_base_url: str = _DEFAULT_INFERENCE_URL,
    ) -> None:
        self._client = client
        self._token_provider = token_provider
        self._base = inference_base_url.rstrip("/")

    async def invoke(
        self, agent_id: str, user_prompt: str, options: StackSpotAgentOptions
    ) -> AgentReply:
        token = await self._token_provider.get_token()
        url = f"{self._base}/v1/agent/{agent_id}/chat"
        try:
            response = await self._client.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=build_payload(user_prompt=user_prompt, streaming=False, options=options),
            )
        except httpx.HTTPError as exc:
            raise UpstreamError(f"falha ao contatar o StackSpot: {exc}") from exc

        if response.status_code == 404:
            raise UpstreamError(f"agent não encontrado: {agent_id!r}", status_code=404)
        if response.status_code >= 400:
            raise UpstreamError(
                f"StackSpot retornou {response.status_code}", status_code=response.status_code
            )

        parsed = StackSpotChatResponse.model_validate(response.json())
        return AgentReply(
            message=parsed.message,
            stop_reason=parsed.stop_reason,
            usage=usage_from_tokens(parsed.tokens),
        )
