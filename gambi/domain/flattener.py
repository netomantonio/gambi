"""ConversationFlattener — D2/D3 da arquitetura.

A Agents API do StackSpot recebe um único `user_prompt`, não um array `messages`.
O v1 é stateless: serializamos a conversa inteira em um prompt com marcadores de papel,
preservando o system prompt do cliente como contexto (o agent já tem o seu próprio).
"""

from __future__ import annotations

from gambi.domain.models import Conversation, Role

_ROLE_LABEL = {
    Role.SYSTEM: "Sistema",
    Role.USER: "Usuário",
    Role.ASSISTANT: "Assistente",
    Role.TOOL: "Ferramenta",
}


class ConversationFlattener:
    """Achata uma `Conversation` em um `user_prompt` único e determinístico."""

    def flatten(self, conversation: Conversation) -> str:
        # Atalho: conversa de um único turno de usuário vira o texto cru,
        # sem marcadores — é o caso mais comum e o mais limpo para o agent.
        if len(conversation.messages) == 1 and conversation.messages[0].role == Role.USER:
            return conversation.messages[0].content.strip()

        blocks: list[str] = []
        for msg in conversation.messages:
            label = _ROLE_LABEL[msg.role]
            blocks.append(f"[{label}]\n{msg.content.strip()}")
        return "\n\n".join(blocks)
