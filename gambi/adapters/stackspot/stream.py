"""StackSpotAgentStreamer — implementa AgentStreamPort via httpx streaming.

Formato confirmado por captura (2026-06-15): SSE com frames `data: {<objeto>}`, onde `<objeto>`
tem o MESMO shape da resposta não-streaming (`{message, stop_reason, tokens, ...}`).
O consumidor é robusto e NÃO depende do content-type:
  - se aparecerem frames `data:`, processa em tempo real (streaming);
  - se nenhum frame `data:` aparecer, trata o corpo inteiro como JSON único (fallback);
  - auto-detecta `message` incremental vs cumulativo (heurística startswith em `_compute_delta`);
  - captura stop_reason/tokens/conversation_id do frame que os trouxer (tipicamente o último).
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import httpx

from gambi.adapters.stackspot.request_payload import build_payload
from gambi.adapters.stackspot.sources import extract_sources
from gambi.adapters.stackspot.tokens import usage_from_tokens
from gambi.application.ports import TokenProviderPort
from gambi.domain.models import AgentStreamEvent, StackSpotAgentOptions, UpstreamError, Usage

logger = logging.getLogger("gambi.stackspot.stream")

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
    ) -> None:
        self._client = client
        self._token_provider = token_provider
        self._base = inference_base_url.rstrip("/")

    async def stream(
        self, agent_id: str, user_prompt: str, options: StackSpotAgentOptions
    ) -> AsyncIterator[AgentStreamEvent]:
        token = await self._token_provider.get_token()
        url = f"{self._base}/v1/agent/{agent_id}/chat"
        payload = build_payload(user_prompt=user_prompt, streaming=True, options=options)
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

                logger.info(
                    "StackSpot stream: status=%s content-type=%r",
                    resp.status_code,
                    resp.headers.get("content-type", ""),
                )
                async for event in self._consume(resp):
                    yield event
        except httpx.HTTPError as exc:
            # Cobre TLS/proxy corporativo, timeout, DNS — causas comuns no corp env.
            logger.exception("falha de transporte ao contatar o StackSpot (stream)")
            raise UpstreamError(f"falha ao contatar o StackSpot (stream): {exc}") from exc

    async def _consume(self, resp: httpx.Response) -> AsyncIterator[AgentStreamEvent]:
        """Processa frames `data:` em tempo real; se não houver frames, cai p/ JSON único."""
        acc = ""
        final_stop: str | None = None
        final_usage: Usage | None = None
        final_conv: str | None = None
        final_sources: tuple[str, ...] = ()
        saw_frame = False
        emitted = False
        buffer: list[str] = []  # só p/ o fallback de JSON único (enquanto não há frames)

        async for raw_line in resp.aiter_lines():
            line = raw_line.strip()
            if not saw_frame and len(buffer) < 500:
                buffer.append(raw_line)
            if not line or line.startswith(":"):  # vazio ou comentário/heartbeat SSE
                continue
            if not line.startswith("data:"):  # ignora event:/id: durante o stream
                continue

            saw_frame = True
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            text, stop, usage, conv, sources = _parse_chunk(payload)
            if stop is not None:
                final_stop = stop
            if usage is not None:
                final_usage = usage
            if conv is not None:
                final_conv = conv
            if sources:
                final_sources = sources
            if text:
                delta, acc = _compute_delta(text, acc)
                if delta:
                    emitted = True
                    yield AgentStreamEvent(delta=delta)

        if not saw_frame:
            # Não era SSE: o corpo inteiro é um JSON único (ou texto cru).
            async for event in self._emit_single_body("\n".join(buffer)):
                yield event
            return

        if not emitted:
            logger.warning(
                "SSE sem conteúdo extraído — formato inesperado. Prévia: %r", buffer[:10]
            )
        yield AgentStreamEvent(
            final=True,
            stop_reason=final_stop,
            usage=final_usage,
            conversation_id=final_conv,
            sources=final_sources,
        )

    async def _emit_single_body(self, raw: str) -> AsyncIterator[AgentStreamEvent]:
        raw = raw.strip()
        try:
            data = json.loads(raw)
        except ValueError:
            logger.warning("corpo não-JSON do StackSpot; primeiros 300 chars: %r", raw[:300])
            if raw:
                yield AgentStreamEvent(delta=raw)
            yield AgentStreamEvent(final=True)
            return
        if not isinstance(data, dict):
            yield AgentStreamEvent(delta=raw)
            yield AgentStreamEvent(final=True)
            return
        text, stop, usage, conv, sources = _parse_chunk_obj(data)
        if text:
            yield AgentStreamEvent(delta=text)
        yield AgentStreamEvent(
            final=True, stop_reason=stop, usage=usage, conversation_id=conv, sources=sources
        )


def _compute_delta(text: str, acc: str) -> tuple[str, str]:
    """Resolve incremental vs cumulativo. Retorna (delta_a_emitir, novo_acumulado)."""
    if acc and text.startswith(acc):
        return text[len(acc) :], text  # cumulativo → só o sufixo novo
    return text, acc + text  # incremental → o próprio chunk


def _parse_chunk(
    payload: str,
) -> tuple[str | None, str | None, Usage | None, str | None, tuple[str, ...]]:
    try:
        obj = json.loads(payload)
    except (ValueError, TypeError):
        return payload, None, None, None, ()  # texto puro
    if not isinstance(obj, dict):
        return str(obj), None, None, None, ()
    return _parse_chunk_obj(obj)


def _parse_chunk_obj(
    obj: dict,
) -> tuple[str | None, str | None, Usage | None, str | None, tuple[str, ...]]:
    text = _extract_text(obj)
    stop = obj.get("stop_reason")
    usage = usage_from_tokens(obj.get("tokens")) if obj.get("tokens") is not None else None
    conv = obj.get("conversation_id")
    sources = extract_sources(obj.get("knowledge_source_id"), obj.get("source"))
    return text, stop, usage, conv, sources


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
