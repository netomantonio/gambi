"""Portas (interfaces) que os adapters de saída implementam.

O domínio/aplicação dependem destas abstrações, nunca de httpx/FastAPI.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from gambi.domain.models import AgentReply, AgentStreamEvent, CatalogEntry


class TokenProviderPort(Protocol):
    async def get_token(self) -> str:
        """Retorna um Bearer token válido para o StackSpot (com cache/refresh)."""
        ...


class AgentInvokerPort(Protocol):
    async def invoke(self, agent_id: str, user_prompt: str) -> AgentReply:
        """Executa um agent (streaming=false) e devolve a resposta normalizada."""
        ...


class AgentStreamPort(Protocol):
    def stream(self, agent_id: str, user_prompt: str) -> AsyncIterator[AgentStreamEvent]:
        """Executa um agent em streaming, emitindo eventos normalizados.

        Implementação defensiva: o formato do SSE do StackSpot é OQ-1 (desconhecido).
        """
        ...


class AgentCatalogPort(Protocol):
    def list_models(self) -> list[CatalogEntry]:
        """Lista os agents expostos como modelos OpenAI."""
        ...

    def resolve(self, model_id: str) -> str | None:
        """Resolve um `model` OpenAI para o `agentId` do StackSpot, ou None."""
        ...
