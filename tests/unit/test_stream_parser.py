"""Testes do parser defensivo de SSE do StackSpot (OQ-1).

Cobrem os formatos plausíveis: texto puro, JSON incremental, JSON cumulativo,
JSON estilo OpenAI, e a extração de metadados finais.
"""

from gambi.adapters.stackspot.stream import (
    _compute_delta,
    _extract_text,
    _extract_usage,
    _parse_chunk,
)


def test_compute_delta_incremental():
    # API incremental: cada chunk é só o pedaço novo.
    d1, acc = _compute_delta("Olá", "")
    assert d1 == "Olá"
    d2, acc = _compute_delta(" mundo", acc)
    assert d2 == " mundo"
    assert acc == "Olá mundo"


def test_compute_delta_cumulative():
    # API cumulativa: cada chunk repete tudo + o novo. Emitimos só o sufixo.
    d1, acc = _compute_delta("Olá", "")
    assert d1 == "Olá"
    d2, acc = _compute_delta("Olá mundo", acc)
    assert d2 == " mundo"
    assert acc == "Olá mundo"


def test_parse_chunk_plain_text():
    text, stop, usage, conv = _parse_chunk("pedaço de texto")
    assert text == "pedaço de texto"
    assert stop is None and usage is None and conv is None


def test_parse_chunk_json_message_key():
    text, stop, usage, conv = _parse_chunk('{"message": "oi", "stop_reason": "stop"}')
    assert text == "oi"
    assert stop == "stop"


def test_parse_chunk_json_openai_style_delta():
    text, _, _, _ = _parse_chunk('{"choices": [{"delta": {"content": "abc"}}]}')
    assert text == "abc"


def test_parse_chunk_final_metadata():
    payload = '{"conversation_id": "01K9", "tokens": {"user": 3, "enrichment": 2, "output": 5}}'
    text, stop, usage, conv = _parse_chunk(payload)
    assert conv == "01K9"
    assert usage.prompt_tokens == 5  # user + enrichment
    assert usage.completion_tokens == 5


def test_extract_text_prefers_known_keys():
    assert _extract_text({"answer": "x"}) == "x"
    assert _extract_text({"foo": "bar"}) is None


def test_extract_usage_none_when_absent():
    assert _extract_usage(None) is None
    assert _extract_usage({"output": 7}).completion_tokens == 7
