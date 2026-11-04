"""The family's `crawl` task (see scrape.json). Try it without the hub: python crawl.py --local [url] The pool worker runs it with the assignment's env and:
SCRAPE_POOL_PROJECT (which project), SCRAPE_JOB_INDEX / SCRAPE_TOTAL_JOBS (this worker's slice), SCRAPE_MAX_HOURS (time budget).

It claims queue items from the hub, fetches each page politely (threads and delay come from the hub on every call), keeps the
raw page in the family's bucket (the hub signs the upload; this code never holds a storage key), stores one record per page,
and reports the standard counters (n_http, t_http_s, http_error, http_<code>) the hub uses for politeness and tracking.
"""
import gzip
import html
import json
import os
import re
import sys
import time

import requests

PROJECT = os.environ.get("SCRAPE_POOL_PROJECT", "")
SITE = os.environ.get("SITE", "https://janaushadhi.gov.in")
DEADLINE = time.time() + float(os.environ.get("SCRAPE_MAX_HOURS", "1")) * 3600 - 120
UA = "s1d-labs scraper (https://github.com/s1d-labs)"
LINK = re.compile(r'<a\b[^>]*?href=["\']([^"\'#][^"\']*)["\']', re.I)
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)


def parse(page, url=""):
    """[(record_id, data)] for one page. Discovery version: title and links, to learn the site's layout from the stored HTML."""
    from urllib.parse import urljoin, urlparse
    title = TITLE.search(page)
    links = sorted({urljoin(url or SITE + "/", h.strip()) for h in LINK.findall(page)})
    host = urlparse(SITE).netloc.removeprefix("www.")
    links = [l for l in links if urlparse(l).netloc.removeprefix("www.") == host]
    rid = re.sub(r"[^A-Za-z0-9._-]+", "_", urlparse(url).path.strip("/") or "home")
    return [(rid, {"url": url, "title": html.unescape(title.group(1)).strip() if title else "", "bytes": len(page), "links": links})]


class LocalHub:
    """Stand-in for HubClient so `--local` runs without the hub: counters go to stderr, records to stdout."""
    settings = {"threads": 1, "delay_ms": 0, "paused": False}

    def __init__(self):
        self.counts = {}

    def metric(self, name, value=1):
        self.counts[name] = self.counts.get(name, 0) + value

    def error(self, n=1):
        self.metric("errors", n)

    def block(self, n=1):
        self.metric("blocked", n)


def local(url):
    hub = LocalHub()
    page = fetch(hub, requests.Session(), url)
    rows = parse(page, url) if page else []
    for rid, data in rows:
        print(json.dumps({"record_id": rid, "data": data}, ensure_ascii=False))
    print(f"{len(rows)} records, counters {hub.counts}", file=sys.stderr)


def fetch(hub, session, url):
    t = time.time()
    try:
        r = session.get(url, timeout=30, headers={"User-Agent": UA})
    except requests.RequestException:
        hub.metric("http_error")
        hub.error()
        return None
    hub.metric("n_http")
    hub.metric("t_http_s", time.time() - t)
    if r.status_code != 200:
        hub.metric(f"http_{r.status_code}")
        if r.status_code in (403, 429, 503):
            hub.block()
        return None
    if not r.encoding or r.encoding.lower() == "iso-8859-1":     # no charset declared: requests guesses Latin-1; trust the content
        r.encoding = r.apparent_encoding or "utf-8"
    return r.text


API = os.environ.get("API", "https://janaushadhi.gov.in:8443")
LIST_KEYS = ("productId", "kendraId", "id", "storeCode", "kendraCode", "applicationId", "drugCode")


def guest_token(hub, session):
    """The site gives every visitor a guest token and sends it as a bearer token on its public API."""
    r = session.get(API + "/auth/generateGuestToken", timeout=30, headers={"User-Agent": UA})
    hub.metric("n_http")
    r.raise_for_status()
    return r.json()["responseBody"]


def rows_of(body):
    """The largest list inside the API's responseBody (newProductResponsesList for products), and the site's total if given."""
    if isinstance(body, list):
        return body, None
    lists = [v for v in (body or {}).values() if isinstance(v, list)]
    return (max(lists, key=len) if lists else []), (body or {}).get("totalElement")


def parse_api(kind, body, page):
    """[(record_id, data)] from one API answer. Pure: test it on saved answers."""
    rows, _ = rows_of(body)
    out = []
    for n, row in enumerate(rows):
        key = next((str(row[k]) for k in LIST_KEYS if isinstance(row, dict) and row.get(k) not in (None, "")), None)
        rid = f"{kind}-{key}" if key else f"{kind}-p{page}-{n}"
        out.append((rid, row))
    return out


def fetch_api(hub, session, token, key, path, payload):
    """The answer's responseBody, or None after hub.failure() recorded why (status, responseCode, message)."""
    t = time.time()
    try:
        r = session.post(API + path, json=payload, timeout=60, headers={"User-Agent": UA, "Authorization": f"Bearer {token}"})
    except requests.RequestException as e:
        hub.metric("http_error")
        hub.error()
        hub.failure("api", key, f"request failed: {type(e).__name__}")
        return None
    hub.metric("n_http")
    hub.metric("t_http_s", time.time() - t)
    if r.status_code != 200:
        hub.metric(f"http_{r.status_code}")
        if r.status_code in (401, 403, 429, 503):
            hub.block()
        hub.failure("api", key, f"HTTP {r.status_code}", body=r.text[:200])
        return None
    try:
        data = r.json()
    except ValueError:
        hub.failure("api", key, "answer is not JSON", body=r.text[:200])
        return None
    if not isinstance(data, dict) or data.get("responseCode") not in (200, None):
        hub.failure("api", key, f"responseCode {data.get('responseCode') if isinstance(data, dict) else '?'}",
                    message=str(data.get("message") or data.get("responseMessage") or "")[:200] if isinstance(data, dict) else "")
        return None
    hub.clear_failure("api", key)
    return data.get("responseBody")


def get_json(hub, session, token, key, path):
    """GET a list the site's own pages load (states, districts): the answer's responseBody, or None after hub.failure()."""
    t = time.time()
    try:
        r = session.get(API + path, timeout=60, headers={"User-Agent": UA, "Authorization": f"Bearer {token}"})
    except requests.RequestException as e:
        hub.metric("http_error")
        hub.error()
        hub.failure("api", key, f"request failed: {type(e).__name__}")
        return None
    hub.metric("n_http")
    hub.metric("t_http_s", time.time() - t)
    if r.status_code != 200:
        hub.metric(f"http_{r.status_code}")
        hub.failure("api", key, f"HTTP {r.status_code}", body=r.text[:200])
        return None
    try:
        data = r.json()
    except ValueError:
        hub.failure("api", key, "answer is not JSON", body=r.text[:200])
        return None
    return data.get("responseBody") if isinstance(data, dict) else None


def first_id(row, names=("id", "stateId", "districtId", "stateCode")):
    return next((row[k] for k in names if isinstance(row, dict) and row.get(k) not in (None, "")), None)


def crawl_kendras(hub, session, token, key, deadline):
    """Every Kendra (store), state by state as the site's own locator asks: [(record id, data)], or None when a state fails."""
    states = get_json(hub, session, token, key, "/api/kendra/getAllStateOfIndia")
    if not isinstance(states, list) or not states:
        return None
    out, seen = [], set()
    if all(first_id(st) is None for st in states):
        hub.failure("api", key, "state rows have no id", sample=json.dumps(states[0], ensure_ascii=False)[:300])
        return None
    for st in states:
        sid = first_id(st)
        if sid is None or time.time() > deadline:
            continue
        sid = str(sid)
        for size in (0, 1000):                          # the site's locator sends 0 (all); some servers want a number
            body = fetch_api(hub, session, token, f"{key}/{sid}", "/api/v1/website/getAllKendraByStateDistrict",
                             {"pageIndex": 0, "pageSize": size, "stateId": sid, "pinCode": 0, "storeCode": ""})
            rows, total = rows_of(body) if body is not None else ([], None)
            if rows:
                break
        if not rows:
            if body is not None:
                hub.failure("api", f"{key}/{sid}", "no rows", total=total, keys=",".join(map(str, list(body)[:8])) if isinstance(body, dict) else type(body).__name__)
            continue
        hub.upload_many([(f"api/kendras-state-{re.sub(r'[^A-Za-z0-9._-]', '_', sid)}.json.gz",
                          gzip.compress(json.dumps(body, ensure_ascii=False).encode()), "application/gzip")])
        for rid, data in parse_api("kendra", body, int(sid) if sid.isdigit() else 0):
            if rid not in seen:
                seen.add(rid)
                out.append((rid, {**data, "state_id": sid, "state": st if not isinstance(st, dict) else {k: v for k, v in st.items() if not isinstance(v, (list, dict))}}))
        time.sleep(max(0.5, hub.settings.get("delay_ms", 0) / 1000))
    return out


def main():
    from scrape_hub_client import HubClient      # imported here so --local works without it
    hub = HubClient(PROJECT, job_index=int(os.environ.get("SCRAPE_JOB_INDEX", "0")), total_jobs=int(os.environ.get("SCRAPE_TOTAL_JOBS", "1")))
    session = requests.Session()
    token = None
    try:
        while time.time() < DEADLINE:
            if hub.settings.get("paused"):
                time.sleep(30)                          # the hub holds us (site down, or the family owner paused it)
                continue
            items = hub.claim(1, steal=True, retry_failed=True)
            if not items:
                break                                   # nothing left for this project: exit, the worker asks the hub for more
            item = items[0]
            if item["payload"].get("kind") == "kendra-all":
                token = token or guest_token(hub, session)
                rows = crawl_kendras(hub, session, token, item["key"], DEADLINE)
                if not rows:
                    token = None
                    hub.complete([item["key"]], "failed", error="no Kendras fetched (see the failures list)")
                    continue
                for rid, data in rows:
                    hub.record(rid, data)
                hub.complete([item["key"]], "done", fetched=len(rows))
                continue
            if "api" in item["payload"]:
                token = token or guest_token(hub, session)
                body = fetch_api(hub, session, token, item["key"], item["payload"]["api"], item["payload"]["body"])
                if body is None:
                    token = None                         # may have expired: fetch a new one next time
                    hub.complete([item["key"]], "failed", error="api call failed")
                    continue
                kind, pg = item["payload"]["kind"], item["payload"]["body"].get("pageIndex", 0)
                hub.upload_many([(f"api/{item['key']}.json.gz", gzip.compress(json.dumps(body, ensure_ascii=False).encode()), "application/gzip")])
                rows = parse_api(kind, body, pg)
                for rid, data in rows:
                    hub.record(rid, {**data, "page": item["key"]}) if isinstance(data, dict) else hub.record(rid, {"value": data, "page": item["key"]})
                hub.complete([item["key"]], "done", fetched=len(rows))
                time.sleep(max(0.5, hub.settings.get("delay_ms", 0) / 1000))
                continue
            page = fetch(hub, session, item["payload"]["url"])
            if page is None:
                hub.complete([item["key"]], "failed", error="page did not load")
                continue
            hub.upload_many([(f"pages/{item['key']}.html.gz", gzip.compress(page.encode()), "application/gzip")])
            rows = parse(page, item["payload"]["url"])
            for rid, data in rows:
                hub.record(rid, {**data, "page": item["key"]})
            hub.complete([item["key"]], "done", fetched=len(rows))
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
