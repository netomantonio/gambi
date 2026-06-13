"""Schemas pydantic da borda StackSpot (Agents API). Ver docs/stackspot/02-agents-api.md."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StackSpotTokens(BaseModel):
    user: int = 0
    enrichment: int = 0
    output: int = 0


class StackSpotChatResponse(BaseModel):
    """Corpo da resposta de POST /v1/agent/{agentId}/chat (streaming=false)."""

    message: str = ""
    stop_reason: str | None = None
    tokens: StackSpotTokens = Field(default_factory=StackSpotTokens)
    conversation_id: str | None = None
