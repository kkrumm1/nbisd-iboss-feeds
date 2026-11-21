#!/usr/bin/env python3
"""Scrape the FreeDNS (afraid.org) shared-domain registry directly.

Based on 4ngel2769/freedns.afraid.org-domain-scraper (page-N.html URLs + browser headers),
with NBISD safety checks. Outputs:
  afraid_all_domains.txt     every registry domain (public + private)
  afraid_public_domains.txt  public only (anyone can create subdomains)
Exits non-zero (and writes nothing) if the scrape looks incomplete.
"""
import os
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

BASE = "https://freedns.afraid.org/domain/registry/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://freedns.afraid.org/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}
MAX_PAGES = 400
OUTPUTS = {"afraid_all_domains.txt": (None, 15000), "afraid_public_domains.txt": ("public", 3000)}
MAX_CHANGE = 0.10
DOMAIN_RE = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")
PROTECTED = {
    "google.com", "googleapis.com", "gstatic.com", "youtube.com", "microsoft.com",
    "office.com", "live.com", "apple.com", "icloud.com", "amazonaws.com",
    "cloudflare.com", "github.com", "githubusercontent.com", "nbisd.org",
    "classlink.com", "instructure.com", "parentsquare.com", "ibosscloud.com",
    "iboss.com", "jamfcloud.com", "magicschool.ai", "clever.com", "afraid.org",
}


def protected(d):
    return any(d == p or d.endswith("." + p) for p in PROTECTED)


def fetch(session, page):
    url = BASE if page == 1 else f"{BASE}page-{page}.html"
    for attempt in range(5):
        try:
            r = session.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200 and len(r.text) > 1000:
                return r.text
            print(f"page {page}: HTTP {r.status_code}, {len(r.text)} bytes", file=sys.stderr)
        except requests.RequestException as e:
            print(f"page {page}: {e}", file=sys.stderr)
        time.sleep(10 * (attempt + 1))
    sys.exit(f"page {page} failed 5 times - keeping old feeds")


def parse(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.find_all("tr", class_=["trd", "trl"]):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue
        dom = tds[0].get_text("\n").split("\n")[0].strip().lower().rstrip(".")
        status = tds[1].get_text().strip().lower()
        if DOMAIN_RE.match(dom):
            rows.append((dom, status))
    last = max([int(n) for n in re.findall(r"page-(\d+)\.html", html)] or [1])
    return rows, last


def main():
    s = requests.Session()
    html = fetch(s, 1)
    rows, last = parse(html)
    if not rows:
        sys.exit("page 1 had no domain rows - afraid.org blocked us or the layout changed")
    last = min(last, MAX_PAGES)
    print(f"registry pages: {last}")
    page = 2
    while page <= last:
        time.sleep(2)
        r, l2 = parse(fetch(s, page))
        if not r:
            sys.exit(f"page {page} had no domain rows - keeping old feeds")
        rows += r
        last = min(max(last, l2), MAX_PAGES)
        page += 1
    seen = {}
    for d, st in rows:
        if not protected(d):
            seen[d] = st
    print(f"domains: {len(seen)} (public {sum(v == 'public' for v in seen.values())})")
    results = {}
    for out, (want, minimum) in OUTPUTS.items():
        doms = sorted(d for d, st in seen.items() if want is None or st == want)
        if len(doms) < minimum:
            sys.exit(f"{out}: only {len(doms)} - keeping old feeds")
        if os.path.exists(out) and os.environ.get("FORCE") != "1":
            old = sum(1 for x in open(out) if x.strip())
            if old and abs(len(doms) - old) / old > MAX_CHANGE:
                sys.exit(f"{out}: {old} -> {len(doms)} (>10%) - keeping old feeds; rerun with force")
        results[out] = doms
    for out, doms in results.items():
        with open(out, "w") as f:
            f.write("\n".join(doms) + "\n")
    print("source: direct scrape")


if __name__ == "__main__":
    main()
