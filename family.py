"""What this family scrapes. Change this file first.

FAMILY must equal the repo name (s1d-labs/<FAMILY>) and the family the hub owner added on scrape.s1d.me/runners.
Each project is one queue of work on one site; `target` is the host it hits (the hub caps workers per target).
"""
import json
import re
from pathlib import Path

FAMILY = json.loads((Path(__file__).parent / "scrape.json").read_text())["family"]

SITE = "https://janaushadhi.gov.in"

API = "https://janaushadhi.gov.in:8443"
PRODUCT_PAGES, PRODUCT_PAGE_SIZE = 25, 100       # the site lists 2,445 products (totalPages 25 at 100 per page)

# list name -> (pages, records the site lists); 100 rows per page, except "achievement" (the site gives 10 per page)
MOSPI_LISTS = {"release": (2, 113), "publication": (3, 255), "announcement": (1, 48), "publicdoc": (1, 99), "ddp": (1, 1), "dg": (1, 11),
               "diid": (1, 60), "administration": (1, 80), "sdmx": (1, 34), "sdg": (1, 23), "achievement": (6, 58)}

# public pages of eaindustry.nic.in found by a small crawl on 2026-11-17 (login pages of the data-submission portals left out)
EA_PAGES = ["/",
    "/about_us.asp",
    "/archive.asp",
    "/contactus.asp",
    "/district_development_plan.asp",
    "/download_data_0405.asp",
    "/download_data_1112.asp",
    "/download_data_2223.asp",
    "/download_data_8182.asp",
    "/download_data_9394.asp",
    "/grievances.asp",
    "/hindi/about_us.asp",
    "/hindi/archive.asp",
    "/hindi/contactus.asp",
    "/hindi/download_data_0405.asp",
    "/hindi/download_data_1112.asp",
    "/hindi/download_data_8182.asp",
    "/hindi/download_data_9394.asp",
    "/hindi/experimental_sp_index.asp",
    "/hindi/ici_press_release_archive.asp",
    "/hindi/linking_factor0405.asp",
    "/hindi/linking_factor1112.asp",
    "/hindi/linking_factor9394.asp",
    "/hindi/price_data_links.asp",
    "/hindi/recruitment.asp",
    "/hindi/rti.asp",
    "/hindi/screen_reader.asp",
    "/hindi/six_infra.asp",
    "/hindi/tenders.asp",
    "/hindi/trade_and_fiscal_policy.asp",
    "/hindi/who_is_who.asp",
    "/hindi/work_allocation.asp",
    "/hindi/wpi_linking_factor.asp",
    "/hindi/wpi_press_release_archive.asp",
    "/hindi/wpi_revision_0405.asp",
    "/ici_download_data.asp",
    "/ici_press_release_archive.asp",
    "/linking_factor0405.asp",
    "/linking_factor1112.asp",
    "/linking_factor2223.asp",
    "/linking_factor9394.asp",
    "/photo_gallery.asp",
    "/photo_gallery1.asp",
    "/photo_gallery2.asp",
    "/price_data_links.asp",
    "/recruitment.asp",
    "/rti.asp",
    "/six_infra.asp",
    "/trade_and_fiscal_policy.asp",
    "/who_is_who.asp",
    "/wpi_linking_factor.asp",
    "/wpi_press_release_archive.asp",
    "/wpi_revision_0405.asp"]

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
        "items": [
            {"key": "home", "payload": {"url": "https://cpwd.gov.in/", "expected": 1}},
            {"key": "home-2", "payload": {"url": "https://cpwd.gov.in/", "expected": 1}},
        ],
    },
    {
        "name": f"{FAMILY}-mospi",
        "title": "MoSPI (Ministry of Statistics and Programme Implementation): releases, reports, documents",
        "task": "mospi",
        "target": "mospi.gov.in",
        "env": {"SITE": "https://www.mospi.gov.in"},
        "threads": 1, "delay_ms": 1500,             # the site answers from outside India: plain GitHub runners, no proxy
        "probe": None,
        "unit_label": "page", "record_label": "record",
        # the site's own public JSON API (what its web pages call): one item per page of one list; the task also keeps the attached files
        "items": [{"key": f"{name}-p{n}" if n == 1 and name != "achievement" else f"{name}-p{n}-r{3 if name == 'achievement' else 2}",   # "-r2": pages 2+ first ran with the wrong paging field (page 1 again), so they got new keys (achievement: wrong again, "-r3")
                   "payload": {"list": name, "page": n, "expected": min(100 if name != "achievement" else 10, total - (n - 1) * (100 if name != "achievement" else 10))}}
                  for name, (pages, total) in MOSPI_LISTS.items() for n in range(1, pages + 1)],
    },
    {
        "name": f"{FAMILY}-eaindustry",
        "title": "Office of Economic Adviser (DPIIT): WPI, PPI, core industries data and press releases",
        "task": "eaindustry",
        "target": "eaindustry.nic.in",
        "env": {"SITE": "https://eaindustry.nic.in"},
        "proxy": "IN",                          # the site answers only from India: GitHub workers through the team's Indian proxies
        "threads": 1, "delay_ms": 1500,
        "probe": None,
        "unit_label": "page", "record_label": "page",
        # one item per public page; the task keeps the raw HTML and downloads the files the page links to (PDF, DOC, XLS)
        "items": [{"key": re.sub(r"[^a-z0-9]+", "-", p.strip("/").lower()).strip("-") or "home",
                   "payload": {"url": "https://eaindustry.nic.in" + p, "expected": 1}} for p in EA_PAGES],
    },
]

PROBES = []
