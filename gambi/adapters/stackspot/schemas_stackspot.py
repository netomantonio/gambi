"""Schemas pydantic da borda StackSpot (Agents API). Ver docs/stackspot/02-agents-api.md."""

from __future__ import annotations

from pydantic import BaseModel


class StackSpotChatResponse(BaseModel):
    """Corpo da resposta de POST /v1/agent/{agentId}/chat.

    `tokens` é deixado como dict cru (formato real: {user,enrichment,input,output} com
    user/enrichment podendo ser null) e resolvido por adapters/stackspot/tokens.py.
    Campos extras observados (message_id, agent_info, source, ...) são ignorados.
    """

    message: str = ""
    stop_reason: str | None = None
    tokens: dict | None = None
    conversation_id: str | None = None
    knowledge_source_id: list | None = None
    source: list | None = None
