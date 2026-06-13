from gambi.domain.flattener import ConversationFlattener
from gambi.domain.models import Conversation, Message, Role

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
