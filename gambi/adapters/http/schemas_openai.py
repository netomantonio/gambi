"""Schemas pydantic do contrato OpenAI (borda inbound)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# --- /v1/models ---


class Model(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int = 0
    owned_by: str = "stackspot"


class ModelList(BaseModel):
    object: Literal["list"] = "list"
    data: list[Model]


# --- /v1/chat/completions (request) ---


class ChatMessage(BaseModel):
    role: str
    # `content` pode ser string ou lista (multimodal). v1 trata só string;
    # partes não-texto são ignoradas na normalização (ver routes_chat).
    content: str | list[dict] | None = None
    # Mensagens de resultado de ferramenta (role="tool") trazem estes:
    name: str | None = None
    tool_call_id: str | None = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    stream: bool = False
    # Parâmetros LLM são aceitos no schema mas ignorados (D4 — fixos no agent).
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    # Tool calling (agent mode do VS Code). Aceitos para NÃO dar 422, mas ainda
    # NÃO suportados: o StackSpot não expõe tool_calls. Ver routes_chat (aviso em log).
    tools: list[dict] | None = None
    tool_choice: object | None = None


# --- /v1/chat/completions (response) ---


class ToolCallFunction(BaseModel):
    name: str
    arguments: str  # string JSON, como no contrato OpenAI


class ResponseToolCall(BaseModel):
    id: str
    type: Literal["function"] = "function"
    function: ToolCallFunction


class ResponseMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str | None = None
    tool_calls: list[ResponseToolCall] | None = None


class Choice(BaseModel):
    index: int = 0
    message: ResponseMessage
    finish_reason: str


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: Usage


# --- erro (envelope OpenAI) ---


class ErrorBody(BaseModel):
    message: str
    type: str
    code: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
