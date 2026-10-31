"""Parsing tests on a saved page: fast, no network."""
from pathlib import Path

import crawl

PAGES = Path(__file__).parent / "pages"


def test_discovery_record_has_title_and_same_site_links():
    (rid, data), = crawl.parse((PAGES / "sample.html").read_text(encoding="utf-8"), "https://janaushadhi.gov.in/")
    assert rid == "home" and data["title"] == "Jan Aushadhi & more"
    assert data["links"] == ["https://janaushadhi.gov.in/about"]
