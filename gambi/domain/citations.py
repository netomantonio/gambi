"""Formatação do rodapé de citações de Knowledge Sources (opt-in por agent)."""

from __future__ import annotations


def format_sources_footer(sources: tuple[str, ...]) -> str:
    """Rodapé markdown com as fontes; string vazia se não houver fontes."""
    if not sources:
        return ""
    return "\n\n---\nFontes: " + ", ".join(sources)
