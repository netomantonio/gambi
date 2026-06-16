"""Normaliza as Knowledge Sources que o StackSpot reporta na resposta → tupla de strings.

A resposta traz `knowledge_source_id` e `source` (quando `return_ks_in_response`). Os formatos
exatos não são 100% documentados, então extraímos de forma tolerante: strings diretas ou um
campo legível (name/id/slug) de dicts. Dedup preservando ordem.
"""

from __future__ import annotations


def extract_sources(knowledge_source_id: object, source: object) -> tuple[str, ...]:
    out: list[str] = []
    for raw in (source, knowledge_source_id):  # `source` primeiro (tende a ser mais legível)
        if not isinstance(raw, list):
            continue
        for item in raw:
            if isinstance(item, str) and item:
                out.append(item)
            elif isinstance(item, dict):
                value = item.get("name") or item.get("slug") or item.get("id")
                if isinstance(value, str) and value:
                    out.append(value)
    seen: set[str] = set()
    deduped = [s for s in out if not (s in seen or seen.add(s))]
    return tuple(deduped)
