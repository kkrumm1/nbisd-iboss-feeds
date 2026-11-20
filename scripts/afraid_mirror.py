#!/usr/bin/env python3
"""Mirror the FreeDNS (afraid.org) shared-domain registry for iboss.

Source: 4ngel2769/freedns.afraid.org-domain-scraper (scheduled scrape of the FreeDNS
registry, published as a markdown table). The run fails - and keeps the old feeds - if
the upstream scrape is older than MAX_AGE_DAYS or looks broken.
Outputs:
  afraid_all_domains.txt     every registry domain (public + private)
  afraid_public_domains.txt  public only (anyone can create subdomains)
"""
import datetime
import os
import re
import sys
import urllib.request

SRC = "https://raw.githubusercontent.com/4ngel2769/freedns.afraid.org-domain-scraper/main/domains-alphabetical.md"
MAX_AGE_DAYS = 14
ROW_RE = re.compile(
    r"^\|\s*([a-z0-9.-]+\.[a-z0-9-]+)\s.*?\|\s*(public|private)\s*\|.*?\|\s*(\d+) days ago \((\d\d)/(\d\d)/(\d{4})\)",
    re.I,
)
OUTPUTS = {  # file: (filter, minimum count)
    "afraid_all_domains.txt": (lambda s: True, 15000),
    "afraid_public_domains.txt": (lambda s: s == "public", 3000),
}
MAX_CHANGE = 0.10  # fail if a list's count moves more than 10% vs the current file
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
    rows, scraped = [], []
    for line in text.splitlines():
        m = ROW_RE.match(line)
        if not m:
            continue
        dom, status, ago, mm, dd, yy = m.groups()
        rows.append({"domain": dom, "status": status})
        scraped.append(datetime.date(int(yy), int(mm), int(dd)) + datetime.timedelta(days=int(ago)))
    if not rows:
        sys.exit("upstream format changed - keeping old feeds")
    newest = max(scraped)
    age = (datetime.date.today() - newest).days
    print(f"upstream scrape date: {newest} ({age} days old)")
    if age > MAX_AGE_DAYS:
        sys.exit(f"upstream scrape is {age} days old - keeping old feeds")

    clean, dropped = [], []
    for row in rows:
        d = (row.get("domain") or "").strip().lower().rstrip(".")
        if not DOMAIN_RE.match(d):
            continue
        if protected(d):
            dropped.append(d)
            continue
        clean.append((d, (row.get("status") or "").strip().lower()))
    print(f"upstream rows: {len(rows)}  protected dropped: {dropped or 'none'}")

    results = {}
    for out, (keep, minimum) in OUTPUTS.items():
        doms = sorted({d for d, s in clean if keep(s)})
        n = len(doms)
        print(f"{out}: {n}")
        if n < minimum:
            sys.exit(f"{out}: only {n} domains - keeping old feeds")
        if os.path.exists(out) and os.environ.get("FORCE") != "1":
            old = sum(1 for line in open(out) if line.strip())
            if old and abs(n - old) / old > MAX_CHANGE:
                sys.exit(f"{out}: count changed {old} -> {n} (>10%) - keeping old feeds; rerun with force")
        results[out] = doms
    for out, doms in results.items():
        with open(out, "w") as f:
            f.write("\n".join(doms) + "\n")


if __name__ == "__main__":
    main()
