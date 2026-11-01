"""Parsing tests on a saved page: fast, no network."""
from pathlib import Path

import crawl

PAGES = Path(__file__).parent / "pages"


def test_discovery_record_has_title_and_same_site_links():
    (rid, data), = crawl.parse((PAGES / "sample.html").read_text(encoding="utf-8"), "https://janaushadhi.gov.in/")
    assert rid == "home" and data["title"] == "Jan Aushadhi & more"
    assert data["links"] == ["https://janaushadhi.gov.in/about"]


def test_api_rows_become_records_with_the_sites_ids():
    body = {"totalElement": 2, "newProductResponsesList": [{"drugCode": 12, "name": "A"}, {"name": "B"}]}
    assert crawl.rows_of(body)[1] == 2
    rows = crawl.parse_api("product", body, 3)
    assert [r for r, _ in rows] == ["product-12", "product-p3-1"]
