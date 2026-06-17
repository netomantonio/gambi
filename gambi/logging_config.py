"""Configuração de logging do GAMBI.

Sem isto, os logs `gambi.*` podem não aparecer no console do uvicorn — o que deixa
falhas (auth, proxy/TLS, formato de SSE) invisíveis. Nível via env GAMBI_LOG_LEVEL.
"""

from __future__ import annotations

import logging
import os


def configure_logging(level: str | None = None) -> None:
    resolved = (level or os.environ.get("GAMBI_LOG_LEVEL", "INFO")).upper()
    logger = logging.getLogger("gambi")
    logger.setLevel(resolved)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
    logger.propagate = False  # evita log duplicado com o root do uvicorn

    # Wide events (CAP-6): logger dedicado, linha crua (JSON ou key=value), sem o prefixo
    # asctime/level — para a linha ser parseável por um agregador. Não propaga p/ `gambi`.
    events = logging.getLogger("gambi.events")
    events.setLevel("INFO")
    if not events.handlers:
        events_handler = logging.StreamHandler()
        events_handler.setFormatter(logging.Formatter("%(message)s"))
        events.addHandler(events_handler)
    events.propagate = False

    # GAMBI_LOG_FILE: captura confiável em arquivo (sem depender de pipe do shell — no Windows,
    # `2>&1 | Tee` no PowerShell 5.1 estraga as linhas). Wide events vão crus; diagnósticos
    # `gambi.*` vão com prefixo. Ambos no MESMO arquivo (append).
    log_file = os.environ.get("GAMBI_LOG_FILE", "").strip()
    if log_file:
        if not any(isinstance(h, logging.FileHandler) for h in events.handlers):
            events_file = logging.FileHandler(log_file, encoding="utf-8")
            events_file.setFormatter(logging.Formatter("%(message)s"))
            events.addHandler(events_file)
        if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
            gambi_file = logging.FileHandler(log_file, encoding="utf-8")
            gambi_file.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
            )
            logger.addHandler(gambi_file)
