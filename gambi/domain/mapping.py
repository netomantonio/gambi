"""Mapeamento da resposta StackSpot → resultado OpenAI (D8 / OQ-6)."""

from __future__ import annotations

import logging

from gambi.domain.models import AgentReply, ChatResult, FinishReason

logger = logging.getLogger("gambi.mapping")

# Valores conhecidos de `stop_reason` do StackSpot → finish_reason OpenAI.
# OQ-6: a doc só confirma "stop"; demais valores são inferência conservadora
# e devem ser revisados quando observados na API real.
_FINISH_REASON = {
    "stop": FinishReason.STOP,
    "length": FinishReason.LENGTH,
    "max_tokens": FinishReason.LENGTH,
    "content_filter": FinishReason.CONTENT_FILTER,
}


class FinishReasonMapper:
    def map(self, stop_reason: str | None) -> FinishReason:
        if stop_reason is None:
            return FinishReason.STOP
        mapped = _FINISH_REASON.get(stop_reason.lower())
        if mapped is None:
            # Não inventar: desconhecido vira STOP (seguro p/ o cliente) + log p/ rastrear OQ-6.
            logger.warning("stop_reason desconhecido do StackSpot: %r → 'stop'", stop_reason)
            return FinishReason.STOP
        return mapped


class ResponseMapper:
    def __init__(self, finish_reason_mapper: FinishReasonMapper | None = None) -> None:
        self._finish = finish_reason_mapper or FinishReasonMapper()

    def to_chat_result(self, reply: AgentReply, model_id: str) -> ChatResult:
        # O uso já vem resolvido na borda (adapters/stackspot/tokens.py).
        return ChatResult(
            model_id=model_id,
            content=reply.message,
            finish_reason=self._finish.map(reply.stop_reason),
            usage=reply.usage,
        )
