"""What this family scrapes. Change this file first.

FAMILY must equal the repo name (s1d-labs/<FAMILY>) and the family the hub owner added on scrape.s1d.me/runners.
Each project is one queue of work on one site; `target` is the host it hits (the hub caps workers per target).
"""
import json
from pathlib import Path

FAMILY = json.loads((Path(__file__).parent / "scrape.json").read_text())["family"]

SITE = "https://janaushadhi.gov.in"

PROJECTS = [
    {
        "name": f"{FAMILY}-janaushadhi",
        "title": "Jan Aushadhi (PMBJP) site",
        "task": "crawl",
        "target": "janaushadhi.gov.in",
        "env": {"SITE": SITE},
        "geo": "IN",                             # the site refuses foreign IPs: only the India pool servers take this work
        "probe": None,                           # the hub checks probes from outside India, which would hold the work
        "unit_label": "page", "record_label": "page",
        # discovery run: one item per start page; the raw HTML goes to the bucket so the real parser can be written from it
        "items": [{"key": "home", "payload": {"url": SITE + "/", "expected": 1}}],
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
