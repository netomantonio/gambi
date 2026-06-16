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

from gambi.domain.models import ToolCall


def parse_structured_response(message: str) -> tuple[str | None, tuple[ToolCall, ...]]:
    """Retorna (content, tool_calls). content=None quando há tool_calls."""
    try:
        data = json.loads(message)
    except (ValueError, TypeError):
        return message, ()  # não é JSON → texto puro
    if not isinstance(data, dict) or "action" not in data:
        return message, ()  # não é o nosso schema → texto puro

    if data.get("action") == "tool_call":
        calls = _extract_tool_calls(data.get("tool_calls"))
        if calls:
            return None, calls

    content = data.get("content")
    return (content if isinstance(content, str) else ""), ()


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
