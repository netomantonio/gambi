"""Configuração de observabilidade via env (CAP-6 / AD-4).

Privacidade em camadas:
  GAMBI_LOG_BODIES=1   inclui corpos (payload/erro) truncados + redacted
  GAMBI_LOG_RAW=1      inclui corpos crus, sem corte/redaction (debug) — implica corpos
  GAMBI_LOG_FORMAT     "json" (um objeto por linha) | "console" (default, key=value)
  GAMBI_LOG_MAX_BODY   limite de chars no truncamento (default 2000)
"""

from __future__ import annotations

import os
from dataclasses import dataclass

_TRUTHY = {"1", "true", "yes", "on"}


def _flag(env: dict[str, str], name: str) -> bool:
    return env.get(name, "").strip().lower() in _TRUTHY


@dataclass(frozen=True)
class ObservabilityConfig:
    log_bodies: bool = False
    log_raw: bool = False
    log_format: str = "console"  # "console" | "json"
    max_body: int = 2000

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> ObservabilityConfig:
        env = env if env is not None else dict(os.environ)
        fmt = env.get("GAMBI_LOG_FORMAT", "console").strip().lower()
        if fmt not in ("console", "json"):
            fmt = "console"
        try:
            max_body = int(env.get("GAMBI_LOG_MAX_BODY", "2000"))
        except ValueError:
            max_body = 2000
        return cls(
            log_bodies=_flag(env, "GAMBI_LOG_BODIES"),
            log_raw=_flag(env, "GAMBI_LOG_RAW"),
            log_format=fmt,
            max_body=max_body,
        )

    @property
    def include_bodies(self) -> bool:
        """raw é um superset de bodies (corpos crus)."""
        return self.log_bodies or self.log_raw
