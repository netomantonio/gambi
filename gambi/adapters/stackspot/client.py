"""StackSpotAgentInvoker — implementa AgentInvokerPort via httpx (NÃO-streaming).

Endpoint: POST {inference_base_url}/v1/agent/{agentId}/chat
Ver docs/stackspot/02-agents-api.md.

NOTA: este é o invoker NÃO-streaming (`streaming:False`). Ele esbarra no teto de ~120s do
gateway do StackSpot em respostas longas (turnos agênticos pesados → `RemoteProtocolError`).
Por isso o composition root (`gambi/main.py`) usa o `BufferedAgentStreamInvoker` (streaming +
acumulação) por padrão. Esta classe segue válida como adapter alternativo p/ chamadas curtas
ou ambientes sem o teto, e mantém a mesma observabilidade (enrich do wide event).
"""

from __future__ import annotations

import time

import httpx

from gambi.adapters.stackspot.request_payload import build_payload
from gambi.adapters.stackspot.schemas_stackspot import StackSpotChatResponse
from gambi.adapters.stackspot.sources import extract_sources
from gambi.adapters.stackspot.tokens import usage_from_tokens
from gambi.application.ports import TokenProviderPort
from gambi.domain.models import AgentReply, StackSpotAgentOptions, UpstreamError
from gambi.observability import enrich
from gambi.observability.config import ObservabilityConfig

_DEFAULT_INFERENCE_URL = "https://genai-inference-app.stackspot.com"


class StackSpotAgentInvoker:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        token_provider: TokenProviderPort,
        inference_base_url: str = _DEFAULT_INFERENCE_URL,
        observability: ObservabilityConfig | None = None,
    ) -> None:
        self._client = client
        self._token_provider = token_provider
        self._base = inference_base_url.rstrip("/")
        self._obs = observability or ObservabilityConfig()

    async def invoke(
        self, agent_id: str, user_prompt: str, options: StackSpotAgentOptions
    ) -> AgentReply:
        token = await self._token_provider.get_token()
        url = f"{self._base}/v1/agent/{agent_id}/chat"
        # Wide event (CAP-6): metadados baratos sempre; corpo do erro só sob flag.
        enrich(upstream_url=url, prompt_chars=len(user_prompt))
        if self._obs.include_bodies:
            enrich(
                upstream_request_body=str(
                    build_payload(user_prompt=user_prompt, streaming=False, options=options)
                )
            )
        start = time.perf_counter()
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
            # Sem resposta HTTP (timeout de leitura, conexão derrubada pelo gateway, TLS...).
            # error_detail = classe+msg do httpx → distingue ReadTimeout de servidor-desconectou.
            enrich(
                upstream_latency_ms=round((time.perf_counter() - start) * 1000, 3),
                error_detail=f"{type(exc).__name__}: {exc}",
            )
            raise UpstreamError(f"falha ao contatar o StackSpot: {exc}") from exc

        enrich(
            upstream_status=response.status_code,
            upstream_latency_ms=round((time.perf_counter() - start) * 1000, 3),
        )
        if response.status_code >= 400:
            # Mata o buraco do 502 cego: capturamos o motivo real do StackSpot (sob flag).
            body = response.text if self._obs.include_bodies else None
            if body is not None:
                enrich(upstream_error_body=body)
            if response.status_code == 404:
                raise UpstreamError(
                    f"agent não encontrado: {agent_id!r}", status_code=404, body=body
                )
            raise UpstreamError(
                f"StackSpot retornou {response.status_code}",
                status_code=response.status_code,
                body=body,
            )

        parsed = StackSpotChatResponse.model_validate(response.json())
        return AgentReply(
            message=parsed.message,
            stop_reason=parsed.stop_reason,
            usage=usage_from_tokens(parsed.tokens),
            sources=extract_sources(parsed.knowledge_source_id, parsed.source),
        )
