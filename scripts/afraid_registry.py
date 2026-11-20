#!/usr/bin/env python3
"""Pull every shared domain from the FreeDNS (afraid.org) public registry
and write a plain domain list for iboss External Threat Feeds.

Output: afraid_org_domains.txt  (one domain per line, sorted, no comments)
"""
import re
import sys
import time
import urllib.request

BASE = "https://freedns.afraid.org/domain/registry/?page={page}&sort=2&q="
UA = "Mozilla/5.0 (NBISD threat-feed builder; contact: NBISD Technology)"
OUT = "afraid_org_domains.txt"
DOMAIN_LINK = re.compile(r'edit_domain_id=\d+[^>]*>\s*([a-z0-9.-]+\.[a-z]{2,})\s*<', re.I)
PAGE_LINK = re.compile(r'[?&]page=(\d+)')
MIN_EXPECTED = 1000  # refuse to overwrite the feed with a broken/partial pull


def fetch(page: int) -> str:
    req = urllib.request.Request(BASE.format(page=page), headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:  # retry with backoff
            print(f"page {page} attempt {attempt + 1} failed: {e}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    raise SystemExit(f"giving up on page {page}")


def main() -> None:
    first = fetch(1)
    last = max([int(p) for p in PAGE_LINK.findall(first)] or [1])
    print(f"registry pages: {last}")
    domains = set(d.lower() for d in DOMAIN_LINK.findall(first))
    for page in range(2, last + 1):
        html = fetch(page)
        found = DOMAIN_LINK.findall(html)
        if not found:
            print(f"page {page}: no domains found", file=sys.stderr)
        domains.update(d.lower() for d in found)
        time.sleep(1.5)  # be polite to afraid.org
    domains.add("afraid.org")
    print(f"domains collected: {len(domains)}")
    if len(domains) < MIN_EXPECTED:
        raise SystemExit(f"only {len(domains)} domains - page format may have changed; keeping old feed")
    with open(OUT, "w") as f:
        f.write("\n".join(sorted(domains)) + "\n")


if __name__ == "__main__":
    main()
