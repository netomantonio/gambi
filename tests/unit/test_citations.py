from gambi.adapters.stackspot.sources import extract_sources
from gambi.domain.citations import format_sources_footer


def test_footer_empty_when_no_sources():
    assert format_sources_footer(()) == ""


def test_footer_lists_sources():
    out = format_sources_footer(("ks-a", "ks-b"))
    assert out.startswith("\n\n")
    assert "Fontes:" in out
    assert "ks-a" in out and "ks-b" in out


def test_extract_sources_strings_and_dicts_dedup_source_first():
    result = extract_sources(["ks-1", "ks-1"], [{"name": "Docs"}, {"id": "x"}, "raw"])
    # `source` vem primeiro; dedup preserva ordem
    assert result == ("Docs", "x", "raw", "ks-1")


def test_extract_sources_tolerates_non_lists():
    assert extract_sources(None, None) == ()
    assert extract_sources("nope", 123) == ()
