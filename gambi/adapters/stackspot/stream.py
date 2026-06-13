"""StackSpotAgentStreamer — implementa AgentStreamPort via httpx streaming.

⚠️ OQ-1: o formato do SSE do StackSpot NÃO é público (ver docs/stackspot/08-gaps-pesquisa.md).
Este parser é DEFENSIVO e auto-descobridor — valide contra a API real no ambiente corporativo:
  - detecta Content-Type: se vier `application/json`, o servidor bufferizou → caminho não-streaming;
  - por linha `data:`, tenta JSON e procura o texto em chaves candidatas; senão usa texto puro;
  - auto-detecta deltas incrementais vs cumulativos (heurística startswith);
  - captura stop_reason/tokens/conversation_id do chunk final quando presentes.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from gambi.application.ports import TokenProviderPort
from gambi.domain.models import AgentStreamEvent, UpstreamError, Usage

_DEFAULT_INFERENCE_URL = "https://genai-inference-app.stackspot.com"

# Ordem de preferência para extrair o texto de um chunk JSON desconhecido.
_TEXT_KEYS = ("message", "answer", "content", "text", "delta")


class StackSpotAgentStreamer:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        token_provider: TokenProviderPort,
        inference_base_url: str = _DEFAULT_INFERENCE_URL,
        stackspot_knowledge: bool = True,
    ) -> None:
        self._client = client
        self._token_provider = token_provider
        self._base = inference_base_url.rstrip("/")
        self._stackspot_knowledge = stackspot_knowledge

    async def stream(self, agent_id: str, user_prompt: str) -> AsyncIterator[AgentStreamEvent]:
        token = await self._token_provider.get_token()
        url = f"{self._base}/v1/agent/{agent_id}/chat"
        payload = {
            "streaming": True,
            "user_prompt": user_prompt,
            "stackspot_knowledge": self._stackspot_knowledge,
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

        try:
            async with self._client.stream("POST", url, headers=headers, json=payload) as resp:
                if resp.status_code == 404:
                    raise UpstreamError(f"agent não encontrado: {agent_id!r}", status_code=404)
                if resp.status_code >= 400:
                    await resp.aread()
                    raise UpstreamError(
                        f"StackSpot retornou {resp.status_code}", status_code=resp.status_code
                    )

                content_type = resp.headers.get("content-type", "")
                if "application/json" in content_type:
                    # Servidor não fez streaming real → re-emite a resposta única como stream.
                    async for event in self._fallback_non_streaming(resp):
                        yield event
                    return

                async for event in self._parse_event_stream(resp):
                    yield event
        except httpx.HTTPError as exc:
            raise UpstreamError(f"falha ao contatar o StackSpot (stream): {exc}") from exc

    async def _fallback_non_streaming(
        self, resp: httpx.Response
    ) -> AsyncIterator[AgentStreamEvent]:
        body = await resp.aread()
        data = json.loads(body)
        text, stop, usage, conv = _parse_chunk_obj(data)
        if text:
            yield AgentStreamEvent(delta=text)
        yield AgentStreamEvent(final=True, stop_reason=stop, usage=usage, conversation_id=conv)

    async def _parse_event_stream(self, resp: httpx.Response) -> AsyncIterator[AgentStreamEvent]:
        acc = ""
        final_stop: str | None = None
        final_usage: Usage | None = None
        final_conv: str | None = None

        async for raw_line in resp.aiter_lines():
            line = raw_line.strip()
            if not line or line.startswith(":"):  # vazio ou comentário/heartbeat SSE
                continue
            payload = line[5:].strip() if line.startswith("data:") else line
            if payload == "[DONE]":
                break

            text, stop, usage, conv = _parse_chunk(payload)
            if stop is not None:
                final_stop = stop
            if usage is not None:
                final_usage = usage
            if conv is not None:
                final_conv = conv
            if text:
                delta, acc = _compute_delta(text, acc)
                if delta:
                    yield AgentStreamEvent(delta=delta)

        yield AgentStreamEvent(
            final=True, stop_reason=final_stop, usage=final_usage, conversation_id=final_conv
        )


def _compute_delta(text: str, acc: str) -> tuple[str, str]:
    """Resolve incremental vs cumulativo. Retorna (delta_a_emitir, novo_acumulado)."""
    if acc and text.startswith(acc):
        return text[len(acc) :], text  # cumulativo → só o sufixo novo
    return text, acc + text  # incremental → o próprio chunk


def _parse_chunk(payload: str) -> tuple[str | None, str | None, Usage | None, str | None]:
    try:
        obj = json.loads(payload)
    except (ValueError, TypeError):
        return payload, None, None, None  # texto puro
    if not isinstance(obj, dict):
        return str(obj), None, None, None
    return _parse_chunk_obj(obj)


def _parse_chunk_obj(obj: dict) -> tuple[str | None, str | None, Usage | None, str | None]:
    text = _extract_text(obj)
    stop = obj.get("stop_reason")
    usage = _extract_usage(obj.get("tokens"))
    conv = obj.get("conversation_id")
    return text, stop, usage, conv


def _extract_text(obj: dict) -> str | None:
    for key in _TEXT_KEYS:
        value = obj.get(key)
        if isinstance(value, str) and value:
            return value
    # formato estilo OpenAI: choices[0].delta.content
    choices = obj.get("choices")
    if isinstance(choices, list) and choices:
        delta = choices[0].get("delta") if isinstance(choices[0], dict) else None
        if isinstance(delta, dict) and isinstance(delta.get("content"), str):
            return delta["content"]
    return None


def _extract_usage(tokens: object) -> Usage | None:
    if not isinstance(tokens, dict):
        return None
    return Usage(
        prompt_tokens=int(tokens.get("user", 0)) + int(tokens.get("enrichment", 0)),
        completion_tokens=int(tokens.get("output", 0)),
    )
