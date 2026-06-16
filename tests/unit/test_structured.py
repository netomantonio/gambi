from gambi.domain.structured import parse_structured_response


def test_parse_final_returns_content():
    p = parse_structured_response('{"action":"final","content":"olá","tool_calls":[]}')
    assert p.content == "olá"
    assert p.tool_calls == ()
    assert p.matched is True


def test_parse_tool_call_returns_tool_calls():
    msg = (
        '{"action":"tool_call","content":"",'
        '"tool_calls":[{"name":"createFile","arguments_json":"{\\"path\\":\\"hello.py\\"}"}]}'
    )
    p = parse_structured_response(msg)
    assert p.content is None
    assert len(p.tool_calls) == 1
    assert p.tool_calls[0].name == "createFile"
    assert p.tool_calls[0].arguments_json == '{"path":"hello.py"}'
    assert p.matched is True


def test_parse_non_json_falls_back_to_plain_text_unmatched():
    p = parse_structured_response("resposta em texto puro")
    assert p.content == "resposta em texto puro"
    assert p.tool_calls == ()
    assert p.matched is False


def test_parse_json_without_action_is_unmatched_plain_text():
    raw = '{"foo":"bar"}'
    p = parse_structured_response(raw)
    assert p.content == raw
    assert p.matched is False


def test_parse_tool_call_tolerates_object_arguments():
    msg = '{"action":"tool_call","tool_calls":[{"name":"x","arguments_json":{"a":1}}]}'
    p = parse_structured_response(msg)
    assert p.tool_calls[0].name == "x"
    assert "1" in p.tool_calls[0].arguments_json  # objeto foi serializado para string JSON
