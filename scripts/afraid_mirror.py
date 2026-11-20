#!/usr/bin/env python3
"""Mirror the PUBLIC FreeDNS (afraid.org) shared domains for iboss.

Source: CodedbyZach/freedns-domain-scraper (hourly scrape of the FreeDNS registry).
Keeps only status=public domains (anyone can create subdomains there - where proxies hide).
Output: afraid_public_domains.txt (one domain per line, sorted)
"""
import csv
import io
import os
import re
import sys
import urllib.request

SRC = "https://raw.githubusercontent.com/CodedbyZach/freedns-domain-scraper/main/domains.csv"
OUT = "afraid_public_domains.txt"
MIN_COUNT = 3000          # sanity floor (registry has ~4,500 public domains)
MAX_CHANGE = 0.10         # fail if count moves more than 10% vs current file
DOMAIN_RE = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")

# Never publish these (or anything under them), whatever the upstream list says.
PROTECTED = {
    "google.com", "googleapis.com", "gstatic.com", "youtube.com", "microsoft.com",
    "office.com", "live.com", "apple.com", "icloud.com", "amazonaws.com",
    "cloudflare.com", "github.com", "githubusercontent.com", "nbisd.org",
    "classlink.com", "instructure.com", "parentsquare.com", "ibosscloud.com",
    "iboss.com", "jamfcloud.com", "magicschool.ai", "clever.com", "afraid.org",
}


def protected(d: str) -> bool:
    return any(d == p or d.endswith("." + p) for p in PROTECTED)


def main() -> None:
    req = urllib.request.Request(SRC, headers={"User-Agent": "nbisd-iboss-feeds"})
    with urllib.request.urlopen(req, timeout=60) as r:
        text = r.read().decode("utf-8", "ignore")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows or "status" not in rows[0] or "domain" not in rows[0]:
        sys.exit("upstream CSV format changed - keeping old feed")

    keep, dropped = set(), []
    for row in rows:
        d = (row.get("domain") or "").strip().lower().rstrip(".")
        if row.get("status", "").strip().lower() != "public" or not DOMAIN_RE.match(d):
            continue
        if protected(d):
            dropped.append(d)
            continue
        keep.add(d)

    n = len(keep)
    print(f"upstream rows: {len(rows)}  public kept: {n}  protected dropped: {dropped or 'none'}")
    if n < MIN_COUNT:
        sys.exit(f"only {n} public domains - keeping old feed")
    if os.path.exists(OUT):
        old = sum(1 for line in open(OUT) if line.strip())
        if old and abs(n - old) / old > MAX_CHANGE and os.environ.get("FORCE") != "1":
            sys.exit(f"count changed {old} -> {n} (>10%) - keeping old feed; rerun with force to accept")
    with open(OUT, "w") as f:
        f.write("\n".join(sorted(keep)) + "\n")


if __name__ == "__main__":
    main()
