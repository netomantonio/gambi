"""Formatação do rodapé de citações de Knowledge Sources (opt-in por agent)."""

from __future__ import annotations


def format_sources_footer(sources: tuple[str, ...]) -> str:
    """Rodapé markdown com as fontes; string vazia se não houver fontes."""
    if not sources:
        return ""
    return "\n\n---\nFontes: " + ", ".join(sources)


def apply_sources_footer(
    content: str | None, *, enabled: bool, sources: tuple[str, ...]
) -> str | None:
    """Anexa o rodapé de fontes ao `content` quando habilitado e há fontes; senão devolve igual."""
    if content is None or not enabled or not sources:
        return content
    return content + format_sources_footer(sources)
