"""Serialização de ChatStreamChunk → SSE no formato OpenAI (chat.completion.chunk + [DONE]).

Contrato confirmado por OQ-2: o VS Code Copilot Chat espera exatamente este formato.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from gambi.domain.models import ChatStreamChunk


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def serialize_openai_sse(
    chunks: AsyncIterator[ChatStreamChunk], *, response_id: str, created: int
) -> AsyncIterator[str]:
    role_sent = False
    async for chunk in chunks:
        base = {
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": chunk.model_id,
        }
        if chunk.delta:
            delta: dict = {}
            if not role_sent:
                delta["role"] = "assistant"
                role_sent = True
            delta["content"] = chunk.delta
            yield _sse({**base, "choices": [{"index": 0, "delta": delta, "finish_reason": None}]})

        if chunk.finish_reason is not None:
            final = {
                **base,
                "choices": [{"index": 0, "delta": {}, "finish_reason": chunk.finish_reason.value}],
            }
            if chunk.usage is not None:
                final["usage"] = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens,
                }
            yield _sse(final)

    yield "data: [DONE]\n\n"
