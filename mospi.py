"""The family's `mospi` task: mospi.gov.in (Ministry of Statistics and Programme Implementation).

The site is a React app. Its pages load lists from its own public JSON API (https://www.mospi.gov.in/api/, POST with a JSON body,
page number in the query). One queue item is one page of one list. For each row the task stores one record and keeps the
attached files (file_one, file_two, file_three, file_url, pdf_file) in the family's bucket through the hub.

Try it without the hub: python mospi.py --local latest-release/get-web-latest-release-list 1
"""
import json
import os
import re
import sys
import time

import requests

PROJECT = os.environ.get("SCRAPE_POOL_PROJECT", "")
SITE = os.environ.get("SITE", "https://www.mospi.gov.in")
DEADLINE = time.time() + float(os.environ.get("SCRAPE_MAX_HOURS", "1")) * 3600 - 120
UA = "s1d-labs scraper (https://github.com/s1d-labs)"
PAGE_SIZE = 100
MAX_FILE = 200 * 1024 * 1024                     # bytes: bigger files are listed as a failure, not downloaded
FILE_KEYS = ("file_one", "file_two", "file_three", "pdf_file", "file_url")

# short name -> (endpoint, extra body). Every list the site's pages use, except the tender list (empty) and
# common-doc/get-web-listing-for-common-web (it needs a source_key that the page gives).
LISTS = {
    "release": ("latest-release/get-web-latest-release-list", {}),
    "publication": ("publications-reports/get-web-publications-report-list", {}),
    "announcement": ("announcement/get-web-announcement-list", {}),
    "publicdoc": ("public-doc/get-web-pub-doc-list", {}),
    "ddp": ("common-doc/get-web-listing-for-ddp", {}),
    "dg": ("common-doc/get-web-listing-for-dg", {}),
    "diid": ("diid/get-web-diid-list", {}),
    "administration": ("administration/get-web-administration-list", {}),
    "sdmx": ("sdmx-doc/get-web-sdmx-doc-list", {}),
    "sdg": ("sdg-documents/get-sdg-web-data", {}),
    "achievement": ("about-us/get-achievements-web", {"sort_field": "published_date", "sort_order": "desc", "limit": 10}),   # this page takes page/limit and a lowercase sort_order
}


def request_body(extra=None, page=1):
    """What the site's own list component sends (page_no is in the body, not in the URL)."""
    body = {"page_no": page, "page": page, "page_size": PAGE_SIZE, "search_term": "", "sort_field": "published_year", "sort_order": "DESC",
            "from_date": "", "to_date": "", "lang": "en", "data_source": "web"}
    body.update(extra or {})
    return body


def parse_list(kind, answer):
    """[(record_id, data)] from one API answer, and the site's total. Pure: test it on saved answers."""
    rows = answer.get("data") if isinstance(answer, dict) else None
    if not isinstance(rows, list):
        return [], None
    pg = answer.get("pagination") or {}
    total = pg.get("totalItems", pg.get("totalRecords", pg.get("total")))
    out = []
    for n, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        rid = f"{kind}-{row['id']}" if row.get("id") not in (None, "") else f"{kind}-p{pg.get('currentPage', 0)}-{n}"
        out.append((rid, row))
    return out, total


def file_refs(row):
    """[(full URL, name, content type, size)] for the files a row points to, on mospi.gov.in only, once each. Pure."""
    from urllib.parse import quote, urljoin, urlsplit
    cands = []
    for k in FILE_KEYS:
        cands.append(row.get(k))
    cands.extend(row.get("doc_url") if isinstance(row.get("doc_url"), list) else [])
    out, seen = [], set()
    for f in cands:
        if isinstance(f, str) and f.strip():
            f = {"path": f.strip()}
        if not (isinstance(f, dict) and isinstance(f.get("path"), str) and f["path"].strip()):
            continue
        u = urlsplit(urljoin(SITE + "/", f["path"].strip()))
        if u.scheme not in ("http", "https") or (u.hostname or "").removeprefix("www.") != "mospi.gov.in":
            continue
        url = f"{SITE}{quote(u.path, safe='/%:@')}"
        if url in seen:
            continue
        seen.add(url)
        out.append((url, f.get("filename") or "", f.get("filemime") or "application/octet-stream", f.get("filesize") or 0))
    return out


def bucket_path(url):
    """Path in the bucket: the file's path on the site, each segment cut to the characters the hub allows."""
    from urllib.parse import unquote, urlsplit
    segs = [re.sub(r"[^A-Za-z0-9._-]+", "_", s) for s in unquote(urlsplit(url).path).split("/") if s not in ("", ".", "..")]
    return "files/" + "/".join(s[:150] for s in segs)


class LocalHub:
    """Stand-in for HubClient so `--local` runs without the hub."""
    settings = {"threads": 1, "delay_ms": 0, "paused": False}

    def __init__(self):
        self.counts = {}

    def metric(self, name, value=1):
        self.counts[name] = self.counts.get(name, 0) + value

    def error(self, n=1):
        self.metric("errors", n)

    def block(self, n=1):
        self.metric("blocked", n)

    def failure(self, *a, **k):
        print("failure", a, k, file=sys.stderr)

    def clear_failure(self, *a):
        pass


def new_session():
    s = requests.Session()
    try:
        from scrape_hub_client import ca_bundle
        s.verify = ca_bundle()
    except ImportError:
        pass
    return s


def api_list(hub, session, key, endpoint, extra, page):
    """The answer (dict) or None after hub.failure() recorded why."""
    t = time.time()
    try:
        r = session.post(f"{SITE}/api/{endpoint}", json=request_body(extra, page), timeout=60,
                         headers={"User-Agent": UA, "Content-Type": "application/json"})
    except requests.RequestException as e:
        hub.metric("http_error")
        hub.error()
        hub.failure("api", key, f"request failed: {type(e).__name__}")
        return None
    hub.metric("n_http")
    hub.metric("t_http_s", time.time() - t)
    if r.status_code != 200:
        hub.metric(f"http_{r.status_code}")
        if r.status_code in (403, 429, 503):
            hub.block()
        hub.failure("api", key, f"HTTP {r.status_code}", body=r.text[:200])
        return None
    try:
        data = r.json()
    except ValueError:
        hub.failure("api", key, "answer is not JSON", body=r.text[:200])
        return None
    if not isinstance(data, dict) or data.get("code") not in (200, None) or data.get("status") == "error":
        hub.failure("api", key, "API error", message=str((data or {}).get("message", ""))[:200] if isinstance(data, dict) else "")
        return None
    hub.clear_failure("api", key)
    return data


def download(hub, session, key, url, size):
    """(bucket path, bytes, content type) or None after hub.failure() recorded why."""
    if size and size > MAX_FILE:
        hub.failure("file", url[-190:], f"file too large ({size} bytes)")
        return None
    t = time.time()
    try:
        r = session.get(url, timeout=120, headers={"User-Agent": UA})
    except requests.RequestException as e:
        hub.metric("http_error")
        hub.error()
        hub.failure("file", url[-190:], f"request failed: {type(e).__name__}")
        return None
    hub.metric("n_http")
    hub.metric("t_http_s", time.time() - t)
    if r.status_code != 200:
        hub.metric(f"http_{r.status_code}")
        if r.status_code in (403, 429, 503):
            hub.block()
        hub.failure("file", url[-190:], f"HTTP {r.status_code}")
        return None
    hub.clear_failure("file", url[-190:])
    return bucket_path(url), r.content, r.headers.get("content-type", "application/octet-stream").split(";")[0]


def process(hub, session, item, fetch_files=True):
    """Handle one queue item: returns the number of records stored, or None when the page failed."""
    p = item["payload"]
    endpoint, extra = LISTS[p["list"]]
    answer = api_list(hub, session, item["key"], endpoint, extra, p["page"])
    if answer is None:
        return None
    rows, total = parse_list(p["list"], answer)
    for rid, row in rows:
        refs = file_refs(row)
        stored = []
        for url, name, ctype, size in refs:
            if not fetch_files or time.time() > DEADLINE:
                continue
            got = download(hub, session, item["key"], url, size)
            time.sleep(max(0.5, hub.settings.get("delay_ms", 0) / 1000))
            if got:
                up = hub.upload_many([got])
                stored.append({"url": url, "bucket_key": up[0]["key"], "bytes": up[0]["bytes"], "sha256": up[0]["sha256"]})
        hub.record(rid, {**row, "list": p["list"], "stored_files": stored, "site_total": total})
    return len(rows)


def local(list_name, page, fetch_files):
    hub = LocalHub()
    session = new_session()
    answer = api_list(hub, session, f"{list_name}-p{page}", *LISTS[list_name], page)
    rows, total = parse_list(list_name, answer or {})
    for rid, data in rows:
        print(json.dumps({"record_id": rid, "data": data, "files": file_refs(data)}, ensure_ascii=False))
    print(f"{len(rows)} records of {total}, counters {hub.counts}", file=sys.stderr)


def main():
    from scrape_hub_client import HubClient
    hub = HubClient(PROJECT, job_index=int(os.environ.get("SCRAPE_JOB_INDEX", "0")), total_jobs=int(os.environ.get("SCRAPE_TOTAL_JOBS", "1")))
    session = new_session()
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
                hub.complete([item["key"]], "failed", error="list page failed (see the failures list)")
            else:
                hub.complete([item["key"]], "done", fetched=n)
            time.sleep(max(0.5, hub.settings.get("delay_ms", 0) / 1000))
        hub.close()
    except BaseException as e:
        hub.close("failed", f"{type(e).__name__}: {e}"[:200])
        raise


if __name__ == "__main__":
    if sys.argv[1:2] == ["--local"]:
        local(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1, False)
    else:
        main()
