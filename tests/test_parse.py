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


def test_crawl_kendras_walks_the_states_the_api_lists():
    class Resp:
        status_code = 200

        def __init__(self, body):
            self.body, self.text = body, ""

        def json(self):
            return {"responseCode": 200, "responseBody": self.body}

    class Session:
        def __init__(self):
            self.posts = []

        def get(self, url, **kw):
            return Resp([{"id": 7, "name": "Delhi"}, {"id": 9, "name": "Goa"}])

        def post(self, url, json=None, **kw):
            self.posts.append(json)
            return Resp({"addKendraResponseList": [{"kendraId": 100 + int(json["stateId"]), "status": 1}, {"kendraId": 1, "status": 1}], "totalElement": 2})

    class Hub:
        settings = {"delay_ms": 0}
        uploads = 0

        def metric(self, *a, **k): pass
        def error(self): pass
        def failure(self, *a, **k): raise AssertionError(a)
        def clear_failure(self, *a): pass
        def upload_many(self, files): self.uploads += len(files)

    crawl.time.sleep = lambda s: None
    s, hub = Session(), Hub()
    rows = crawl.crawl_kendras(hub, s, "token", "kendras-all", crawl.time.time() + 60)
    assert [r for r, _ in rows] == ["kendra-107", "kendra-1", "kendra-109"]      # kendra-1 is on both states: stored once
    assert s.posts[0] == {"pageIndex": 0, "pageSize": 0, "stateId": "7", "pinCode": 0, "storeCode": ""}
    assert hub.uploads == 2 and rows[0][1]["state"] == {"id": 7, "name": "Delhi"}
