"""ConversationFlattener — D2/D3 da arquitetura.

A Agents API do StackSpot recebe um único `user_prompt`, não um array `messages`.
O v1 é stateless: serializamos a conversa inteira em um prompt com marcadores de papel.

Quando o request traz ferramentas (agent mode do VS Code), o prompt é montado no
**contrato de agent mode** que o agent espera (ver docs/stackspot-agent-mode-setup.md):
  ## FERRAMENTAS DISPONÍVEIS / ## CONVERSA / ## RESULTADOS DAS FERRAMENTAS
"""

from __future__ import annotations

from gambi.domain.models import Conversation, Role, ToolSpec

_ROLE_LABEL = {
    Role.SYSTEM: "Sistema",
    Role.USER: "Usuário",
    Role.ASSISTANT: "Assistente",
    Role.TOOL: "Ferramenta",
}


class ConversationFlattener:
    """Achata uma `Conversation` (+ tools) em um `user_prompt` único e determinístico."""

    def flatten(self, conversation: Conversation, tools: tuple[ToolSpec, ...] = ()) -> str:
        if tools:
            return self._agent_mode(conversation, tools)
        return self._plain(conversation)

    def _plain(self, conversation: Conversation) -> str:
        # Atalho: conversa de um único turno de usuário vira o texto cru, sem marcadores.
        if len(conversation.messages) == 1 and conversation.messages[0].role == Role.USER:
            return conversation.messages[0].content.strip()

        blocks: list[str] = []
        for msg in conversation.messages:
            blocks.append(f"[{_ROLE_LABEL[msg.role]}]\n{msg.content.strip()}")
        return "\n\n".join(blocks)

    def _agent_mode(self, conversation: Conversation, tools: tuple[ToolSpec, ...]) -> str:
        sections: list[str] = []

        tool_lines = ["## FERRAMENTAS DISPONÍVEIS"]
        for tool in tools:
            tool_lines.append(f"- nome: {tool.name}")
            tool_lines.append(f"  descrição: {tool.description}")
            tool_lines.append(f"  argumentos: {tool.parameters_json}")
        sections.append("\n".join(tool_lines))

        convo = [m for m in conversation.messages if m.role != Role.TOOL]
        conv_lines = ["## CONVERSA"]
        for msg in convo:
            conv_lines.append(f"[{_ROLE_LABEL[msg.role]}] {msg.content.strip()}")
        sections.append("\n".join(conv_lines))

        results = [m for m in conversation.messages if m.role == Role.TOOL]
        if results:
            res_lines = ["## RESULTADOS DAS FERRAMENTAS"]
            for msg in results:
                res_lines.append(f"- name: {msg.name or 'tool'}")
                res_lines.append(f"  result: {msg.content.strip()}")
            sections.append("\n".join(res_lines))

        return "\n\n".join(sections)
