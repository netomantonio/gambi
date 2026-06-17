"""T2/AC5 — redaction de segredos + truncamento."""

from __future__ import annotations

from gambi.observability.redaction import redact, truncate


def test_redact_bearer_token():
    out = redact("crédito recusado; header foi Bearer abc123.DEF-456 ok")
    assert "abc123.DEF-456" not in out
    assert "***" in out


def test_redact_masks_authorization_value():
    out = redact("Authorization: Bearer abc123.DEF-456")
    assert "abc123" not in out
    assert "***" in out


def test_redact_client_secret_in_json():
    out = redact('{"client_secret": "sup3r-s3cr3t", "x": 1}')
    assert "sup3r-s3cr3t" not in out
    assert "client_secret" in out


def test_redact_api_key_kv():
    out = redact("api_key=zzz999 token=qqq")
    assert "zzz999" not in out
    assert "qqq" not in out


def test_truncate_cuts_with_marker():
    out = truncate("x" * 100, 10)
    assert out.startswith("x" * 10)
    assert "truncado" in out
    assert len(out) < 100


def test_truncate_noop_when_short_or_zero():
    assert truncate("curto", 100) == "curto"
    assert truncate("qualquer", 0) == "qualquer"
