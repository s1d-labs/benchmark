"""What this family scrapes. Change this file first.

FAMILY must equal the repo name (s1d-labs/<FAMILY>) and the family the hub owner added on scrape.s1d.me/runners.
Each project is one queue of work on one site; `target` is the host it hits (the hub caps workers per target).
"""
import json
from pathlib import Path

FAMILY = json.loads((Path(__file__).parent / "scrape.json").read_text())["family"]

SITE = "https://janaushadhi.gov.in"

API = "https://janaushadhi.gov.in:8443"
PRODUCT_PAGES, PRODUCT_PAGE_SIZE = 25, 100       # the site lists 2,445 products (totalPages 25 at 100 per page)

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
                 # every Kendra (store): one item, because the site's locator asks one state at a time (stateId as text, pageSize 0)
                 # and the state list comes from the API itself. "kendras-p0" and "kendras-n0-p0" failed with "server error" (wrong request).
                 + [{"key": "kendras-all", "payload": {"kind": "kendra-all", "expected": 17000}}],
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
    {
        "name": f"{FAMILY}-cpwd",
        "title": "CPWD (Central Public Works Department) site",
        "task": "crawl",
        "target": "cpwd.gov.in",
        "env": {"SITE": "https://cpwd.gov.in"},
        "geo": "IN",                             # the site's HTTPS answers with a reset from the box and from 3 proxy IPs of 2 ranges:
        "proxy": "IN",                           # try both India routes (servers and proxies) and read the run's egress IP
        "proxy_only": ["91.124.42."],            # proxy ranges 191.219.x and 95.134.119.x got a reset on port 443; try the third range
        "threads": 1, "delay_ms": 1500,
        "probe": None,
        "unit_label": "page", "record_label": "page",
        # discovery run: the raw homepage HTML goes to the bucket so the real parser can be written from it
        "items": [{"key": "home", "payload": {"url": "https://cpwd.gov.in/", "expected": 1}}],
    },
]

PROBES = []
