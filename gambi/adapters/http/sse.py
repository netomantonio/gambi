"""Serialização de ChatStreamChunk → SSE no formato OpenAI (chat.completion.chunk + [DONE]).

Contrato confirmado por OQ-2: o VS Code Copilot Chat espera exatamente este formato.

Erros durante o streaming acontecem DEPOIS do HTTP 200 (headers já enviados), então não há
como devolver um status de erro — os exception handlers não se aplicam aqui. Para não falhar
em silêncio (o que deixa o VS Code mostrando "nada"), capturamos, **logamos** e **emitimos o erro
como conteúdo visível** no chat, encerrando o stream corretamente.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator

from gambi.domain.models import ChatStreamChunk

logger = logging.getLogger("gambi.http.sse")


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def serialize_openai_sse(
    chunks: AsyncIterator[ChatStreamChunk], *, response_id: str, created: int, model: str
) -> AsyncIterator[str]:
    base = {
        "id": response_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
    }
    role_sent = False
    try:
        async for chunk in chunks:
            if chunk.delta:
                delta: dict = {}
                if not role_sent:
                    delta["role"] = "assistant"
                    role_sent = True
                delta["content"] = chunk.delta
                yield _sse(
                    {**base, "choices": [{"index": 0, "delta": delta, "finish_reason": None}]}
                )

            if chunk.tool_calls:
                tc_delta: dict = {}
                if not role_sent:
                    tc_delta["role"] = "assistant"
                    role_sent = True
                tc_delta["tool_calls"] = [
                    {
                        "index": i,
                        "id": f"call_{uuid.uuid4().hex}",
                        "type": "function",
                        "function": {"name": tc.name, "arguments": tc.arguments_json},
                    }
                    for i, tc in enumerate(chunk.tool_calls)
                ]
                yield _sse(
                    {**base, "choices": [{"index": 0, "delta": tc_delta, "finish_reason": None}]}
                )

            if chunk.finish_reason is not None:
                final = {
                    **base,
                    "choices": [
                        {"index": 0, "delta": {}, "finish_reason": chunk.finish_reason.value}
                    ],
                }
                if chunk.usage is not None:
                    final["usage"] = {
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens,
                        "total_tokens": chunk.usage.total_tokens,
                    }
                yield _sse(final)
    except Exception as exc:  # noqa: BLE001 — fronteira: re-superfície como erro visível + log
        logger.exception("erro durante o streaming do chat")
        err_delta: dict = {"content": f"\n\n[GAMBI erro: {exc}]"}
        if not role_sent:
            err_delta["role"] = "assistant"
        yield _sse({**base, "choices": [{"index": 0, "delta": err_delta, "finish_reason": None}]})
        yield _sse({**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})

    yield "data: [DONE]\n\n"
