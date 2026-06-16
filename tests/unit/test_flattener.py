from gambi.domain.flattener import ConversationFlattener
from gambi.domain.models import Conversation, Message, Role, ToolSpec

flatten = ConversationFlattener().flatten


def conv(*pairs: tuple[Role, str]) -> Conversation:
    return Conversation(messages=tuple(Message(role=r, content=c) for r, c in pairs))


def test_single_user_message_is_raw_text():
    assert flatten(conv((Role.USER, "  Olá  "))) == "Olá"


def test_system_and_user_get_role_markers():
    result = flatten(conv((Role.SYSTEM, "Seja conciso."), (Role.USER, "O que é uma API?")))
    assert "[Sistema]" in result
    assert "Seja conciso." in result
    assert "[Usuário]" in result
    assert "O que é uma API?" in result


def test_multi_turn_preserves_order():
    result = flatten(
        conv(
            (Role.USER, "primeira"),
            (Role.ASSISTANT, "resposta"),
            (Role.USER, "segunda"),
        )
    )
    assert result.index("primeira") < result.index("resposta") < result.index("segunda")


# --- Agent mode (com tools) ---

_TOOLS = (
    ToolSpec(name="createFile", description="Cria um arquivo", parameters_json='{"type":"object"}'),
)


def test_agent_mode_builds_tools_and_conversation_sections():
    result = flatten(conv((Role.USER, "crie hello.py")), _TOOLS)
    assert "## FERRAMENTAS DISPONÍVEIS" in result
    assert "- nome: createFile" in result
    assert '  argumentos: {"type":"object"}' in result
    assert "## CONVERSA" in result
    assert "[Usuário] crie hello.py" in result
    # sem resultados de ferramenta nesta requisição
    assert "## RESULTADOS DAS FERRAMENTAS" not in result


def test_agent_mode_separates_tool_results_into_their_section():
    conversation = Conversation(
        messages=(
            Message(Role.USER, "crie hello.py"),
            Message(Role.ASSISTANT, ""),
            Message(Role.TOOL, "arquivo criado com sucesso", name="createFile"),
        )
    )
    result = flatten(conversation, _TOOLS)
    assert "## RESULTADOS DAS FERRAMENTAS" in result
    assert "- name: createFile" in result
    assert "  result: arquivo criado com sucesso" in result
    # o resultado da ferramenta NÃO deve aparecer dentro da CONVERSA
    conversa_bloco = result.split("## CONVERSA")[1].split("## RESULTADOS")[0]
    assert "arquivo criado com sucesso" not in conversa_bloco


def test_no_tools_keeps_plain_format():
    # sem tools, mantém o comportamento de chat normal (atalho de turno único)
    assert flatten(conv((Role.USER, "oi"))) == "oi"
