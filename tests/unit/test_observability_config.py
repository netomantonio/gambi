"""T2/AC5-6 — ObservabilityConfig.from_env (flags de verbosidade)."""

from __future__ import annotations

from gambi.observability.config import ObservabilityConfig


def test_defaults_are_safe():
    cfg = ObservabilityConfig.from_env({})
    assert cfg.log_bodies is False
    assert cfg.log_raw is False
    assert cfg.log_format == "console"
    assert cfg.include_bodies is False


def test_bodies_flag_parsed():
    cfg = ObservabilityConfig.from_env({"GAMBI_LOG_BODIES": "1"})
    assert cfg.log_bodies is True
    assert cfg.include_bodies is True


def test_raw_implies_bodies():
    cfg = ObservabilityConfig.from_env({"GAMBI_LOG_RAW": "true"})
    assert cfg.log_raw is True
    assert cfg.include_bodies is True


def test_format_json_and_bad_value_falls_back():
    assert ObservabilityConfig.from_env({"GAMBI_LOG_FORMAT": "json"}).log_format == "json"
    assert ObservabilityConfig.from_env({"GAMBI_LOG_FORMAT": "xml"}).log_format == "console"


def test_max_body_default_and_override():
    assert ObservabilityConfig.from_env({}).max_body == 2000
    assert ObservabilityConfig.from_env({"GAMBI_LOG_MAX_BODY": "50"}).max_body == 50
    assert ObservabilityConfig.from_env({"GAMBI_LOG_MAX_BODY": "abc"}).max_body == 2000
