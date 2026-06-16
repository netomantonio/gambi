"""Parser da saída estruturada do agent (agent mode) → conteúdo ou tool_calls.

Contrato (ver docs/stackspot-agent-mode-setup.md):
  { "action": "tool_call" | "final",
    "content": "<markdown quando final>",
    "tool_calls": [{ "name": "...", "arguments_json": "<string JSON>" }] }

Defensivo: se a `message` não for o nosso JSON (ex.: agent não-estruturado respondeu texto),
cai no fallback e devolve o texto como conteúdo — agent mode degrada para resposta normal.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from gambi.domain.models import ToolCall


@dataclass(frozen=True)
class StructuredParse:
    """Resultado do parse da saída estruturada.

    `matched` indica se a resposta seguiu o nosso schema (tinha `action`). Quando False,
    `content` é o texto cru (fallback) — sinal de que vale um repair retry no agent mode.
    """

    content: str | None
    tool_calls: tuple[ToolCall, ...]
    matched: bool


def parse_structured_response(message: str) -> StructuredParse:
    try:
        data = json.loads(message)
    except (ValueError, TypeError):
        return StructuredParse(content=message, tool_calls=(), matched=False)  # não é JSON
    if not isinstance(data, dict) or "action" not in data:
        return StructuredParse(
            content=message, tool_calls=(), matched=False
        )  # não é o nosso schema

    if data.get("action") == "tool_call":
        calls = _extract_tool_calls(data.get("tool_calls"))
        if calls:
            return StructuredParse(content=None, tool_calls=calls, matched=True)

    content = data.get("content")
    return StructuredParse(
        content=content if isinstance(content, str) else "", tool_calls=(), matched=True
    )


def _extract_tool_calls(raw: object) -> tuple[ToolCall, ...]:
    if not isinstance(raw, list):
        return ()
    calls: list[ToolCall] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not name:
            continue
        args = item.get("arguments_json")
        if not isinstance(args, str):
            # tolera o agent mandar objeto em vez de string JSON
            args = json.dumps(args or {}, ensure_ascii=False)
        calls.append(ToolCall(name=str(name), arguments_json=args))
    return tuple(calls)
