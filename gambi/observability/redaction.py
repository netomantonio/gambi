"""Redaction de segredos + truncamento (CAP-6 / AD-3).

Aplicado pelo emissor antes de escrever corpos. Piso de privacidade: tokens Bearer e
pares chave-segredo (client_secret, api_key, token, authorization) nunca saem em claro
quando corpos são logados.
"""

from __future__ import annotations

import re

_MASK = "***"

# `Bearer <token>`
_BEARER = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]+")

# pares chave-valor sensíveis: client_secret, api_key/api-key, secret, token, authorization
# casa `key: "v"`, `key=v`, `"key": "v"`. Captura a chave+separador, mascara só o valor.
_SECRET_KV = re.compile(
    r"(?i)(\"?(?:client_secret|api[_-]?key|secret|token|authorization)\"?\s*[:=]\s*\"?)"
    r"[^\"'\s,}]+"
)


def redact(text: str) -> str:
    text = _BEARER.sub(rf"\1{_MASK}", text)
    text = _SECRET_KV.sub(rf"\1{_MASK}", text)
    return text


def truncate(text: str, limit: int) -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    return text[:limit] + "…(truncado)"
