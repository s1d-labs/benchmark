"""The family's `eaindustry` task: eaindustry.nic.in (Office of Economic Adviser, DPIIT): WPI / PPI / core industries data, press releases, archives.

The site is classic ASP pages that link to PDF, DOC and Excel files. The site answers only from India (the project runs through the
team's Indian proxies) and its server does not send its intermediate certificate (new_session uses the SDK's ca_bundle).
One queue item is one public page: the task stores the raw HTML, one record for the page (title, links, files) and keeps the files
the page links to, on this host only, in the family's bucket through the hub. Login pages of the data-submission portals are not in the queue.

Try it without the hub, through an Indian proxy: myproxy run python eaindustry.py --local https://eaindustry.nic.in/archive.asp
"""
import gzip
import html
import json
import os
import re
import sys
import time
from urllib.parse import quote, unquote, urldefrag, urljoin, urlsplit

import mospi                                      # shared helpers: LocalHub, new_session, download (checks, metrics, failures), bucket_path

PROJECT = os.environ.get("SCRAPE_POOL_PROJECT", "")
SITE = os.environ.get("SITE", "https://eaindustry.nic.in")
HOST = urlsplit(SITE).hostname
DEADLINE = time.time() + float(os.environ.get("SCRAPE_MAX_HOURS", "1")) * 3600 - 120
LINK = re.compile(r'<a\b[^>]*?href=["\']([^"\'#][^"\']*)["\']', re.I)
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
FILE = re.compile(r"\.(pdf|xlsx?|docx?|pptx?|zip|csv|rar)$", re.I)
PRIVATE = re.compile(r"/(newseries|institutional\w*|pricedata\w*|backlogdata|admin|jobs)/|login|password", re.I)


def parse(page, url):
    """(record id, data, file URLs) for one page. Pure: test it on saved pages."""
    title = TITLE.search(page)
    links, files = set(), set()
    for h in LINK.findall(page):
        u = urldefrag(urljoin(url, html.unescape(h.strip())))[0]
        p = urlsplit(u)
        if p.scheme not in ("http", "https") or p.hostname != HOST or PRIVATE.search(p.path):
            continue
        clean = f"{p.scheme}://{p.netloc}{quote(unquote(p.path), safe='/%:@')}"
        (files if FILE.search(p.path) else links).add(clean)
    rid = re.sub(r"[^A-Za-z0-9._-]+", "_", urlsplit(url).path.strip("/") or "home")
    data = {"url": url, "title": html.unescape(title.group(1)).strip() if title else "", "bytes": len(page),
            "links": sorted(links), "files": sorted(files)}
    return rid, data, sorted(files)


def fetch_page(hub, session, url):
    t = time.time()
    try:
        r = session.get(url, timeout=40, headers={"User-Agent": mospi.UA})
    except mospi.requests.RequestException as e:
        hub.metric("http_error")
        hub.error()
        hub.failure("page", url[-190:], f"request failed: {type(e).__name__}")
        return None
    hub.metric("n_http")
    hub.metric("t_http_s", time.time() - t)
    if r.status_code != 200:
        hub.metric(f"http_{r.status_code}")
        if r.status_code in (403, 429, 503):
            hub.block()
        hub.failure("page", url[-190:], f"HTTP {r.status_code}")
        return None
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding or "utf-8"
    hub.clear_failure("page", url[-190:])
    return r.text


def process(hub, session, item, fetch_files=True):
    """One queue item: returns the number of records stored, or None when the page failed."""
    url = item["payload"]["url"]
    page = fetch_page(hub, session, url)
    if page is None:
        return None
    rid, data, files = parse(page, url)
    hub.upload_many([(f"pages/{item['key']}.html.gz", gzip.compress(page.encode()), "application/gzip")])
    stored = []
    for f in files if fetch_files else []:
        if time.time() > DEADLINE:
            return None                                   # out of time: the hub hands the item to a new run
        time.sleep(max(0.5, hub.settings.get("delay_ms", 0) / 1000))
        got = mospi.download(hub, session, item["key"], f, 0)
        if got:
            up = hub.upload_many([got])
            stored.append({"url": f, "bucket_key": up[0]["key"], "bytes": up[0]["bytes"], "sha256": up[0]["sha256"]})
    hub.record(rid, {**data, "page": item["key"], "stored_files": stored})
    return 1


def local(url):
    hub = mospi.LocalHub()
    page = fetch_page(hub, mospi.new_session(), url)
    if page:
        rid, data, _ = parse(page, url)
        print(json.dumps({"record_id": rid, "data": data}, ensure_ascii=False))
    print(f"counters {hub.counts}", file=sys.stderr)


def main():
    from scrape_hub_client import HubClient
    hub = HubClient(PROJECT, job_index=int(os.environ.get("SCRAPE_JOB_INDEX", "0")), total_jobs=int(os.environ.get("SCRAPE_TOTAL_JOBS", "1")))
    session = mospi.new_session()
    try:
        while time.time() < DEADLINE:
            if hub.settings.get("paused"):
                time.sleep(30)
                continue
            items = hub.claim(1, steal=True, retry_failed=True)
            if not items:
                break
            item = items[0]
            n = process(hub, session, item)
            if n is None:
                hub.complete([item["key"]], "failed", error="page or time budget (see the failures list)")
            else:
                hub.complete([item["key"]], "done", fetched=n)
            time.sleep(max(0.5, hub.settings.get("delay_ms", 0) / 1000))
        hub.close()
    except BaseException as e:
        hub.close("failed", f"{type(e).__name__}: {e}"[:200])
        raise


if __name__ == "__main__":
    if sys.argv[1:2] == ["--local"]:
        local(sys.argv[2] if len(sys.argv) > 2 else SITE + "/")
    else:
        main()
