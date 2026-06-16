"""Testes do parser defensivo de SSE do StackSpot (OQ-1).

Cobrem os formatos plausíveis: texto puro, JSON incremental, JSON cumulativo,
JSON estilo OpenAI, e a extração de metadados finais.
"""

from gambi.adapters.stackspot.stream import (
    _compute_delta,
    _extract_text,
    _parse_chunk,
)
from gambi.adapters.stackspot.tokens import usage_from_tokens


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
    text, stop, usage, conv, sources = _parse_chunk("pedaço de texto")
    assert text == "pedaço de texto"
    assert stop is None and usage is None and conv is None
    assert sources == ()


def test_parse_chunk_json_message_key():
    text, stop, usage, conv, _ = _parse_chunk('{"message": "oi", "stop_reason": "stop"}')
    assert text == "oi"
    assert stop == "stop"


def test_parse_chunk_json_openai_style_delta():
    text, *_ = _parse_chunk('{"choices": [{"delta": {"content": "abc"}}]}')
    assert text == "abc"


def test_parse_chunk_final_metadata():
    payload = (
        '{"conversation_id": "01K9", "tokens": {"user": 3, "enrichment": 2, "output": 5}, '
        '"knowledge_source_id": ["ks-a"]}'
    )
    text, stop, usage, conv, sources = _parse_chunk(payload)
    assert conv == "01K9"
    assert usage.prompt_tokens == 5  # input ausente → user + enrichment
    assert usage.completion_tokens == 5
    assert sources == ("ks-a",)


def test_extract_text_prefers_known_keys():
    assert _extract_text({"answer": "x"}) == "x"
    assert _extract_text({"foo": "bar"}) is None


def test_usage_from_tokens_real_shape_with_nulls():
    # Shape REAL capturado da API (2026-06-15): user/enrichment null, prompt em `input`.
    usage = usage_from_tokens({"user": None, "enrichment": None, "input": 6331, "output": 2970})
    assert usage.prompt_tokens == 6331
    assert usage.completion_tokens == 2970


def test_usage_from_tokens_absent_or_invalid():
    assert usage_from_tokens(None).prompt_tokens == 0
    assert usage_from_tokens({"output": 7}).completion_tokens == 7
    assert usage_from_tokens({"output": 7}).prompt_tokens == 0
