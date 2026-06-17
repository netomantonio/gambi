"""Casos de uso: orquestram domínio + portas. Sem detalhes de framework."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import replace

from gambi.application.ports import AgentCatalogPort, AgentInvokerPort, AgentStreamPort
from gambi.domain.citations import apply_sources_footer, format_sources_footer
from gambi.domain.flattener import ConversationFlattener
from gambi.domain.mapping import FinishReasonMapper, ResponseMapper
from gambi.domain.models import (
    CatalogEntry,
    ChatResult,
    ChatStreamChunk,
    Conversation,
    FinishReason,
    ModelNotFoundError,
    StackSpotAgentOptions,
    ToolSpec,
)
from gambi.domain.structured import parse_structured_response
from gambi.observability import enrich

logger = logging.getLogger("gambi.use_cases")

# Quantas vezes reprompt o agent quando ele não respeita o schema (agent mode).
_MAX_SCHEMA_REPAIRS = 1
_REPAIR_INSTRUCTION = (
    "\n\n## CORREÇÃO\n"
    "Sua resposta anterior NÃO seguiu o schema JSON exigido. "
    "Responda SOMENTE com o objeto JSON do schema, sem texto fora dele."
)


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

    async def execute(
        self,
        model_id: str,
        conversation: Conversation,
        tools: tuple[ToolSpec, ...] = (),
        mode: str = "ask",
    ) -> ChatResult:
        entry = self._catalog.resolve(model_id, mode)
        if entry is None:
            raise ModelNotFoundError(model_id)
        enrich(agent_id=entry.agent_id)  # wide event (CAP-6)

        user_prompt = self._flattener.flatten(conversation, tools)
        reply = await self._invoker.invoke(entry.agent_id, user_prompt, entry.options)

        # Agent estruturado (Structured Output) sempre emite o JSON do nosso schema — mesmo sem
        # tools (ask mode). Parseamos quando há tools OU quando o agent é estruturado.
        if tools or entry.options.structured_output:
            parsed = parse_structured_response(reply.message)
            # Robustez: se o agent não respeitou o schema, reprompt uma vez antes do fallback.
            repairs = 0
            while not parsed.matched and repairs < _MAX_SCHEMA_REPAIRS:
                repairs += 1
                logger.warning("structured output fora do schema; repair retry %d", repairs)
                reply = await self._invoker.invoke(
                    entry.agent_id, user_prompt + _REPAIR_INSTRUCTION, entry.options
                )
                parsed = parse_structured_response(reply.message)
            finish = FinishReason.TOOL_CALLS if parsed.tool_calls else FinishReason.STOP
            # agent_action: o que o agent decidiu (diagnóstico da falha-irmã não-502).
            if parsed.tool_calls:
                action = "tool_call"
            elif parsed.matched:
                action = "final"
            else:
                action = "unmatched"
            enrich(schema_repairs=repairs, agent_action=action, outcome="success")
            content = parsed.content
            if not parsed.tool_calls:  # resposta final → pode receber rodapé de fontes (F)
                content = apply_sources_footer(
                    content, enabled=entry.options.return_ks_in_response, sources=reply.sources
                )
            return ChatResult(
                model_id=model_id,
                content=content,
                finish_reason=finish,
                usage=reply.usage,
                tool_calls=parsed.tool_calls,
            )

        enrich(agent_action="final", schema_repairs=0, outcome="success")
        result = self._mapper.to_chat_result(reply, model_id)
        # F — citações: anexa rodapé "Fontes" quando o agent opta por return_ks_in_response.
        return replace(
            result,
            content=apply_sources_footer(
                result.content, enabled=entry.options.return_ks_in_response, sources=reply.sources
            ),
        )


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
        self,
        model_id: str,
        conversation: Conversation,
        tools: tuple[ToolSpec, ...] = (),
        mode: str = "ask",
    ) -> AsyncIterator[ChatStreamChunk]:
        # Validação ansiosa: resolve/achata ANTES de iniciar o stream, para que um
        # erro (ex.: modelo inexistente) vire HTTP 404 e não um stream meio-aberto.
        entry = self._catalog.resolve(model_id, mode)
        if entry is None:
            raise ModelNotFoundError(model_id)
        enrich(agent_id=entry.agent_id)  # wide event (CAP-6)
        user_prompt = self._flattener.flatten(conversation, tools)
        return self._generate(entry.agent_id, model_id, user_prompt, entry.options)

    async def _generate(
        self, agent_id: str, model_id: str, user_prompt: str, options: StackSpotAgentOptions
    ) -> AsyncIterator[ChatStreamChunk]:
        async for event in self._streamer.stream(agent_id, user_prompt, options):
            if event.delta:
                yield ChatStreamChunk(model_id=model_id, delta=event.delta)
            if event.final:
                # F — citações: rodapé "Fontes" antes do chunk final (opt-in).
                if options.return_ks_in_response and event.sources:
                    yield ChatStreamChunk(
                        model_id=model_id, delta=format_sources_footer(event.sources)
                    )
                yield ChatStreamChunk(
                    model_id=model_id,
                    finish_reason=self._finish.map(event.stop_reason),
                    usage=event.usage,
                )
