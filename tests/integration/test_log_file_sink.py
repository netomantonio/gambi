"""GAMBI_LOG_FILE — captura confiável dos wide events em arquivo (debug no Windows)."""

from __future__ import annotations

import logging

from gambi.logging_config import configure_logging


def test_gambi_log_file_captures_wide_events(tmp_path, monkeypatch):
    log_file = tmp_path / "gambi-debug.log"
    monkeypatch.setenv("GAMBI_LOG_FILE", str(log_file))

    events = logging.getLogger("gambi.events")
    base = logging.getLogger("gambi")
    # snapshot do estado global (handlers + propagate) p/ restaurar — configure_logging muta
    # loggers globais e não pode vazar p/ outros testes (ex.: caplog em test_emit).
    snapshot = [
        (logger, list(logger.handlers), logger.propagate, logger.level)
        for logger in (events, base)
    ]
    try:
        configure_logging()
        events.info('{"request_id":"r1","outcome":"upstream_error","upstream_status":429}')
        for handler in events.handlers:
            handler.flush()
        assert log_file.exists()
        assert "upstream_error" in log_file.read_text(encoding="utf-8")
    finally:
        for logger, handlers, propagate, level in snapshot:
            for handler in list(logger.handlers):
                if handler not in handlers:
                    logger.removeHandler(handler)
                    handler.close()
            logger.propagate = propagate
            logger.setLevel(level)
