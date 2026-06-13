"""Rota POST /v1/chat/completions (CAP-2, não-streaming)."""

from __future__ import annotations

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
    Usage,
)
from gambi.adapters.http.sse import serialize_openai_sse
from gambi.application.use_cases import CreateChatCompletion, CreateChatCompletionStream
from gambi.domain.models import Conversation, Message, Role

router = APIRouter()


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
        Message(role=_to_role(m.role), content=_content_to_text(m.content)) for m in messages
    )
    return Conversation(messages=domain_messages)


def _to_role(role: str) -> Role:
    try:
        return Role(role)
    except ValueError:
        # Papel desconhecido tratado como usuário (conservador).
        return Role.USER


@router.post("/v1/chat/completions")
async def create_chat_completion(body: ChatCompletionRequest, request: Request):
    conversation = _to_conversation(body.messages)

    if body.stream:
        # CAP-3: streaming SSE OpenAI (o que o VS Code Copilot Chat usa).
        stream_uc: CreateChatCompletionStream = request.app.state.create_chat_completion_stream
        # execute() valida o modelo ANTES do stream → erro vira HTTP normal (ex.: 404).
        chunks = await stream_uc.execute(body.model, conversation)
        return StreamingResponse(
            serialize_openai_sse(
                chunks, response_id=f"chatcmpl-{uuid.uuid4().hex}", created=int(time.time())
            ),
            media_type="text/event-stream",
        )

    use_case: CreateChatCompletion = request.app.state.create_chat_completion
    result = await use_case.execute(body.model, conversation)

    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex}",
        created=int(time.time()),
        model=result.model_id,
        choices=[
            Choice(
                message=ResponseMessage(content=result.content),
                finish_reason=result.finish_reason.value,
            )
        ],
        usage=Usage(
            prompt_tokens=result.usage.prompt_tokens,
            completion_tokens=result.usage.completion_tokens,
            total_tokens=result.usage.total_tokens,
        ),
    )
