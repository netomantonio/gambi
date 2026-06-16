from gambi.domain.structured import parse_structured_response


def test_parse_final_returns_content():
    content, calls = parse_structured_response('{"action":"final","content":"olá","tool_calls":[]}')
    assert content == "olá"
    assert calls == ()


def test_parse_tool_call_returns_tool_calls():
    msg = (
        '{"action":"tool_call","content":"",'
        '"tool_calls":[{"name":"createFile","arguments_json":"{\\"path\\":\\"hello.py\\"}"}]}'
    )
    content, calls = parse_structured_response(msg)
    assert content is None
    assert len(calls) == 1
    assert calls[0].name == "createFile"
    assert calls[0].arguments_json == '{"path":"hello.py"}'


def test_parse_non_json_falls_back_to_plain_text():
    content, calls = parse_structured_response("resposta em texto puro")
    assert content == "resposta em texto puro"
    assert calls == ()


def test_parse_json_without_action_is_treated_as_plain_text():
    raw = '{"foo":"bar"}'
    content, calls = parse_structured_response(raw)
    assert content == raw
    assert calls == ()


def test_parse_tool_call_tolerates_object_arguments():
    msg = '{"action":"tool_call","tool_calls":[{"name":"x","arguments_json":{"a":1}}]}'
    _, calls = parse_structured_response(msg)
    assert calls[0].name == "x"
    assert "1" in calls[0].arguments_json  # objeto foi serializado para string JSON
