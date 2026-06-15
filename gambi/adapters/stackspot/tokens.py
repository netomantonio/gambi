"""Resolução do bloco `tokens` do StackSpot → Usage do domínio.

Formato REAL observado na API (2026-06-15):
    {"user": null, "enrichment": null, "input": 6331, "output": 2970}
O total do prompt vem em `input`; `user`/`enrichment` podem ser null (legado/não usados).
Caímos para `user + enrichment` se `input` estiver ausente (compat. com a doc antiga).
"""

from __future__ import annotations

from gambi.domain.models import Usage


def _as_int(value: object) -> int:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def usage_from_tokens(tokens: object) -> Usage:
    if not isinstance(tokens, dict):
        return Usage(prompt_tokens=0, completion_tokens=0)
    prompt = _as_int(tokens.get("input")) or (
        _as_int(tokens.get("user")) + _as_int(tokens.get("enrichment"))
    )
    return Usage(prompt_tokens=prompt, completion_tokens=_as_int(tokens.get("output")))
