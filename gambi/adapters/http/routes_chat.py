"""Rota POST /v1/chat/completions (CAP-2, não-streaming)."""

from __future__ import annotations

import json
import logging
import time
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from gambi.adapters.http.schemas_openai import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    Choice,
    ResponseMessage,
    ResponseToolCall,
    ToolCallFunction,
    Usage,
)
from gambi.adapters.http.sse import serialize_openai_sse
from gambi.application.use_cases import CreateChatCompletion, CreateChatCompletionStream
from gambi.domain.models import ChatResult, ChatStreamChunk, Conversation, Message, Role, ToolSpec

router = APIRouter()
logger = logging.getLogger("gambi.http.chat")


def _content_to_text(content: str | list[dict] | None) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    # Multimodal (lista de partes): v1 só usa as partes de texto (non-goal: imagens).
    parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
    return "\n".join(parts)


def _to_conversation(messages: list[ChatMessage]) -> Conversation:
    domain_messages = tuple(
        Message(
            role=_to_role(m.role),
            content=_content_to_text(m.content),
            # resultado de ferramenta (role="tool") carrega o nome p/ a seção RESULTADOS
            name=m.name or m.tool_call_id,
        )
        for m in messages
    )
    return Conversation(messages=domain_messages)


def _to_role(role: str) -> Role:
    try:
        return Role(role)
    except ValueError:
        # Papel desconhecido tratado como usuário (conservador).
        return Role.USER


def _to_tools(tools: list[dict] | None) -> tuple[ToolSpec, ...]:
    """Converte o array `tools` da OpenAI em ToolSpec do domínio (function calling)."""
    if not tools:
        return ()
    specs: list[ToolSpec] = []
    for tool in tools:
        fn = tool.get("function") if isinstance(tool, dict) else None
        if not isinstance(fn, dict) or not fn.get("name"):
            continue
        specs.append(
            ToolSpec(
                name=str(fn["name"]),
                description=str(fn.get("description", "")),
                parameters_json=json.dumps(fn.get("parameters", {}), ensure_ascii=False),
            )
        )
    return tuple(specs)


def _render_completion(result: ChatResult) -> ChatCompletionResponse:
    if result.tool_calls:
        message = ResponseMessage(
            content=None,
            tool_calls=[
                ResponseToolCall(
                    id=f"call_{uuid.uuid4().hex}",
                    function=ToolCallFunction(name=tc.name, arguments=tc.arguments_json),
                )
                for tc in result.tool_calls
            ],
        )
    else:
        message = ResponseMessage(content=result.content)
    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex}",
        created=int(time.time()),
        model=result.model_id,
        choices=[Choice(message=message, finish_reason=result.finish_reason.value)],
        usage=Usage(
            prompt_tokens=result.usage.prompt_tokens,
            completion_tokens=result.usage.completion_tokens,
            total_tokens=result.usage.total_tokens,
        ),
    )


async def _result_to_chunks(result: ChatResult):
    """Converte um ChatResult (agent mode, já parseado) em chunks p/ o serializador SSE."""
    if result.tool_calls:
        yield ChatStreamChunk(model_id=result.model_id, tool_calls=result.tool_calls)
    elif result.content:
        yield ChatStreamChunk(model_id=result.model_id, delta=result.content)
    yield ChatStreamChunk(
        model_id=result.model_id, finish_reason=result.finish_reason, usage=result.usage
    )


def _sse_response(chunks, *, model: str) -> StreamingResponse:
    return StreamingResponse(
        serialize_openai_sse(
            chunks,
            response_id=f"chatcmpl-{uuid.uuid4().hex}",
            created=int(time.time()),
            model=model,
        ),
        media_type="text/event-stream",
    )


@router.post("/v1/chat/completions")
async def create_chat_completion(body: ChatCompletionRequest, request: Request):
    logger.info(
        "chat: model=%r stream=%s messages=%d tools=%d",
        body.model,
        body.stream,
        len(body.messages),
        len(body.tools or []),
    )
    conversation = _to_conversation(body.messages)
    tools = _to_tools(body.tools)
    use_case: CreateChatCompletion = request.app.state.create_chat_completion

    # Detecção de modo (determinística): sem tools = ask; com tools = agent (cobre edit+agent).
    # Um modelo-alias roteia para agents StackSpot diferentes por modo.
    mode = "agent" if tools else "ask"

    # Agent estruturado sempre emite o JSON do nosso schema → bufferiza+parseia mesmo sem tools
    # (senão, em ask mode, vazaria JSON cru). entry pode ser None (modelo desconhecido) → cai no
    # caminho normal, onde execute() revalida e retorna 404.
    entry = request.app.state.catalog.resolve(body.model, mode)
    structured = bool(entry and entry.options.structured_output)

    if structured or tools:
        # Bufferiza não-stream (precisamos do JSON inteiro p/ parsear em content/tool_calls).
        # execute() valida o modelo ANTES → erro vira HTTP normal (404), sem stream meio-aberto.
        result = await use_case.execute(body.model, conversation, tools, mode)
        if result.tool_calls:
            logger.info("agent mode: %d tool_calls emitidas", len(result.tool_calls))
        if body.stream:
            return _sse_response(_result_to_chunks(result), model=result.model_id)
        return _render_completion(result)

    if body.stream:
        # CAP-3: streaming SSE OpenAI (chat normal, sem tools).
        stream_uc: CreateChatCompletionStream = request.app.state.create_chat_completion_stream
        chunks = await stream_uc.execute(body.model, conversation, tools, mode)
        return _sse_response(chunks, model=body.model)

    result = await use_case.execute(body.model, conversation, tools, mode)
    return _render_completion(result)
