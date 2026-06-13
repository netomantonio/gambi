"""Casos de uso: orquestram domínio + portas. Sem detalhes de framework."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from gambi.application.ports import AgentCatalogPort, AgentInvokerPort, AgentStreamPort
from gambi.domain.flattener import ConversationFlattener
from gambi.domain.mapping import FinishReasonMapper, ResponseMapper
from gambi.domain.models import (
    CatalogEntry,
    ChatResult,
    ChatStreamChunk,
    Conversation,
    ModelNotFoundError,
)

logger = logging.getLogger("gambi.use_cases")


class ListModels:
    def __init__(self, catalog: AgentCatalogPort) -> None:
        self._catalog = catalog

    def execute(self) -> list[CatalogEntry]:
        return self._catalog.list_models()


class CreateChatCompletion:
    """CAP-2: traduz uma conversa OpenAI em execução de agent StackSpot (não-streaming)."""

    def __init__(
        self,
        catalog: AgentCatalogPort,
        invoker: AgentInvokerPort,
        flattener: ConversationFlattener | None = None,
        mapper: ResponseMapper | None = None,
    ) -> None:
        self._catalog = catalog
        self._invoker = invoker
        self._flattener = flattener or ConversationFlattener()
        self._mapper = mapper or ResponseMapper()

    async def execute(self, model_id: str, conversation: Conversation) -> ChatResult:
        agent_id = self._catalog.resolve(model_id)
        if agent_id is None:
            raise ModelNotFoundError(model_id)

        user_prompt = self._flattener.flatten(conversation)
        reply = await self._invoker.invoke(agent_id, user_prompt)
        return self._mapper.to_chat_result(reply, model_id)


class CreateChatCompletionStream:
    """CAP-3: mesma tradução da CAP-2, mas emitindo `chat.completion.chunk` em streaming."""

    def __init__(
        self,
        catalog: AgentCatalogPort,
        streamer: AgentStreamPort,
        flattener: ConversationFlattener | None = None,
        finish_mapper: FinishReasonMapper | None = None,
    ) -> None:
        self._catalog = catalog
        self._streamer = streamer
        self._flattener = flattener or ConversationFlattener()
        self._finish = finish_mapper or FinishReasonMapper()

    async def execute(
        self, model_id: str, conversation: Conversation
    ) -> AsyncIterator[ChatStreamChunk]:
        # Validação ansiosa: resolve/achata ANTES de iniciar o stream, para que um
        # erro (ex.: modelo inexistente) vire HTTP 404 e não um stream meio-aberto.
        agent_id = self._catalog.resolve(model_id)
        if agent_id is None:
            raise ModelNotFoundError(model_id)
        user_prompt = self._flattener.flatten(conversation)
        return self._generate(agent_id, model_id, user_prompt)

    async def _generate(
        self, agent_id: str, model_id: str, user_prompt: str
    ) -> AsyncIterator[ChatStreamChunk]:
        async for event in self._streamer.stream(agent_id, user_prompt):
            if event.delta:
                yield ChatStreamChunk(model_id=model_id, delta=event.delta)
            if event.final:
                yield ChatStreamChunk(
                    model_id=model_id,
                    finish_reason=self._finish.map(event.stop_reason),
                    usage=event.usage,
                )
