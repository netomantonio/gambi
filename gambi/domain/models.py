"""Tipos de domínio. Sem pydantic, sem httpx — só a linguagem do negócio."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


@dataclass(frozen=True)
class Conversation:
    """Uma conversa OpenAI normalizada (lista ordenada de mensagens)."""

    messages: tuple[Message, ...]

    def __post_init__(self) -> None:
        if not self.messages:
            raise EmptyConversationError("conversa sem mensagens")


class FinishReason(StrEnum):
    STOP = "stop"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True)
class AgentReply:
    """Resposta de um agent StackSpot, já normalizada para o domínio.

    O uso de tokens é resolvido na borda (o formato real é `{user,enrichment,input,output}`,
    com user/enrichment podendo ser null — ver adapters/stackspot/tokens.py).
    """

    message: str
    stop_reason: str | None
    usage: Usage = field(default_factory=lambda: Usage(0, 0))


@dataclass(frozen=True)
class ChatResult:
    """Resultado pronto para virar um `chat.completion` OpenAI."""

    model_id: str
    content: str
    finish_reason: FinishReason
    usage: Usage


@dataclass(frozen=True)
class StackSpotAgentOptions:
    """Opções de request do StackSpot por agent (campos confirmados na API real).

    Todos têm default seguro; cada agent pode sobrescrever via configuração.
    """

    stackspot_knowledge: bool = True
    deep_search_ks: bool = False
    return_ks_in_response: bool = False
    knowledge_source_ids: tuple[str, ...] = ()
    agent_version_number: int | None = None


@dataclass(frozen=True)
class CatalogEntry:
    """Um agent StackSpot exposto como 'modelo' OpenAI, com suas opções de request."""

    model_id: str
    agent_id: str
    options: StackSpotAgentOptions = field(default_factory=StackSpotAgentOptions)


@dataclass(frozen=True)
class AgentStreamEvent:
    """Evento normalizado do streaming de um agent (produzido pelo adapter StackSpot).

    Eventos de conteúdo trazem `delta`; o evento final traz `final=True` e os
    metadados de término (stop_reason cru, usage, conversation_id).
    """

    delta: str | None = None
    final: bool = False
    stop_reason: str | None = None
    usage: Usage | None = None
    conversation_id: str | None = None


@dataclass(frozen=True)
class ChatStreamChunk:
    """Pedaço pronto para virar um `chat.completion.chunk` OpenAI."""

    model_id: str
    delta: str | None = None
    finish_reason: FinishReason | None = None
    usage: Usage | None = None


# --- Exceções de domínio (mapeadas para o envelope de erro OpenAI na borda) ---


class DomainError(Exception):
    """Base das falhas de domínio."""


class EmptyConversationError(DomainError):
    """Conversa sem nenhuma mensagem."""


class ModelNotFoundError(DomainError):
    """O `model` pedido não corresponde a nenhum agent no catálogo."""

    def __init__(self, model_id: str) -> None:
        super().__init__(f"modelo desconhecido: {model_id!r}")
        self.model_id = model_id


class UpstreamAuthError(DomainError):
    """Falha ao autenticar contra o StackSpot."""


class UpstreamError(DomainError):
    """Falha do StackSpot ao executar o agent."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
