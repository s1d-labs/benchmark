"""What this family scrapes. Change this file first.

FAMILY must equal the repo name (s1d-labs/<FAMILY>) and the family the hub owner added on scrape.s1d.me/runners.
Each project is one queue of work on one site; `target` is the host it hits (the hub caps workers per target).
"""
import json
from pathlib import Path

FAMILY = json.loads((Path(__file__).parent / "scrape.json").read_text())["family"]

SITE = "https://janaushadhi.gov.in"

API = "https://janaushadhi.gov.in:8443"
PRODUCT_PAGES, PRODUCT_PAGE_SIZE = 2, 100        # first run: 2 pages + the Kendra list; raise to ~40 once it works (pages past the end answer empty)

PROJECTS = [
    {
        "name": f"{FAMILY}-janaushadhi",
        "title": "Jan Aushadhi (PMBJP): products and Kendras",
        "task": "crawl",
        "target": "janaushadhi.gov.in",
        "env": {"SITE": SITE, "API": API},
        "proxy": "IN",                           # site refuses foreign IPs: GitHub workers through the team's Indian proxies
        "threads": 1, "delay_ms": 1500,
        "probe": None,                           # the hub checks probes from outside India, which would hold the work
        "unit_label": "page", "record_label": "record",
        # the site's own public API (what its web pages call), one item per page of results
        "items": [{"key": f"products-p{n}", "payload": {"kind": "product", "api": "/api/v1/website/getAllProductForWeb", "expected": PRODUCT_PAGE_SIZE,
                                                         "body": {"pageIndex": n, "pageSize": PRODUCT_PAGE_SIZE, "searchText": "", "columnName": "drug_code", "orderBy": "asc"}}}
                  for n in range(PRODUCT_PAGES)]
                 + [{"key": "kendras-p0", "payload": {"kind": "kendra", "api": "/api/v1/website/getAllKendraByStateDistrict", "expected": 1000,
                                                      "body": {"pageIndex": 0, "pageSize": 100000, "stateId": 0, "districtId": 0, "pinCode": 0}}}],
    },
    {
        "name": f"{FAMILY}-nppa",
        "title": "NPPA (National Pharmaceutical Pricing Authority) site",
        "task": "crawl",
        "target": "nppa.gov.in",
        "env": {"SITE": "https://nppa.gov.in"},
        "geo": "IN",
        "probe": None,
        "unit_label": "page", "record_label": "page",
        "items": [{"key": "home", "payload": {"url": "https://nppa.gov.in/", "expected": 1}}],
    },
]

PROBES = []
