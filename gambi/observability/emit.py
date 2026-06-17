"""Emissor do wide event (CAP-6 / AD-3, AD-4).

Único ponto que serializa o evento. Aplica o tier de verbosidade (descarta corpos por
default), redaction e truncamento, e escreve uma linha no logger `gambi.events`.
Nunca levanta: observabilidade não pode derrubar a request (núcleo sagrado).
"""

from __future__ import annotations

import json
import logging

from gambi.observability.config import ObservabilityConfig
from gambi.observability.redaction import redact, truncate
from gambi.observability.wide_event import WideEvent

logger = logging.getLogger("gambi.events")

# Metadados: sempre incluídos (quando não-nulos). Ordem estável p/ leitura.
_METADATA_FIELDS = (
    "request_id",
    "method",
    "path",
    "http_status",
    "duration_ms",
    "model",
    "mode",
    "stream",
    "n_messages",
    "n_tools",
    "n_tool_results",
    "tool_names",
    "agent_id",
    "agent_action",
    "schema_repairs",
    "prompt_chars",
    "upstream_url",
    "upstream_status",
    "upstream_latency_ms",
    "outcome",
    "error_type",
    "error_detail",
)

# Corpos: só sob flag (privacidade em camadas).
_BODY_FIELDS = ("upstream_request_body", "upstream_error_body")


def _payload(event: WideEvent, config: ObservabilityConfig) -> dict[str, object]:
    data: dict[str, object] = {}
    for name in _METADATA_FIELDS:
        value = getattr(event, name)
        if value is None or value == []:
            continue
        data[name] = value
    if config.include_bodies:
        for name in _BODY_FIELDS:
            value = getattr(event, name)
            if value is None:
                continue
            text = str(value)
            if not config.log_raw:  # bodies: redige + trunca; raw: cru
                text = truncate(redact(text), config.max_body)
            data[name] = text
    return data


def _fmt(value: object) -> str:
    if isinstance(value, str):
        return value if " " not in value else f'"{value}"'
    return json.dumps(value, ensure_ascii=False)


def emit(event: WideEvent, config: ObservabilityConfig) -> None:
    try:
        data = _payload(event, config)
        if config.log_format == "json":
            logger.info(json.dumps(data, ensure_ascii=False, default=str))
        else:
            logger.info(" ".join(f"{key}={_fmt(value)}" for key, value in data.items()))
    except Exception:  # noqa: BLE001 — observabilidade nunca derruba a request
        logger.warning("falha ao emitir wide event", exc_info=False)
