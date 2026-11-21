#!/usr/bin/env python3
"""Build a hunting list from GitHub-based free-subdomain registries (NOT a block feed).

Each registry keeps one file per subdomain in a public repo. We shallow-clone them and
write free_subdomain_registry.tsv:  hostname <TAB> owner (GitHub user/email) <TAB> target
S&D uses it to spot subdomains whose owner is a known kit GitHub account, and to know
which parent domains are free-subdomain services.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

REGISTRIES = [  # repo, parent used when a record has no domain of its own
    ("is-a-dev/register", "is-a.dev"),
    ("open-domains/register", None),
    ("free-domains/register", None),
    ("is-cool-me/register", None),
    ("is-amazing/register", "is-amaz.ing"),
]
OUT = "free_subdomain_registry.tsv"
HOST_RE = re.compile(r"^[a-z0-9_-]+(\.[a-z0-9_-]+)+$")


def clone(repo, dest):
    r = subprocess.run(["git", "clone", "--depth", "1", "-q", f"https://github.com/{repo}.git", dest],
                       capture_output=True, text=True, timeout=600)
    return r.returncode == 0


def owner_of(rec):
    o = rec.get("owner") or {}
    if isinstance(o, dict):
        return o.get("username") or o.get("github") or o.get("email") or ""
    return str(o)


def target_of(rec):
    r = rec.get("record") or rec.get("records") or {}
    if isinstance(r, dict):
        for k in ("CNAME", "A", "AAAA", "URL"):
            v = r.get(k)
            if v:
                return v if isinstance(v, str) else ",".join(map(str, v))
    return ""


def from_dir(path, parent):
    out = []
    ddir = os.path.join(path, "domains")
    if not os.path.isdir(ddir):
        return out
    for fn in os.listdir(ddir):
        if not fn.endswith(".json"):
            continue
        stem = fn[:-5].lower()
        try:
            rec = json.load(open(os.path.join(ddir, fn), encoding="utf-8"))
        except Exception:
            rec = {}
        if isinstance(rec, dict) and rec.get("domain") and rec.get("subdomain"):
            host = f"{rec['subdomain']}.{rec['domain']}".lower()
        elif "." in stem and parent is None:
            host = stem
        elif parent:
            host = stem if stem.endswith("." + parent) else f"{stem}.{parent}"
        else:
            continue
        if HOST_RE.match(host):
            out.append((host, owner_of(rec) if isinstance(rec, dict) else "", target_of(rec) if isinstance(rec, dict) else ""))
    return out


def jsorg(path):
    out = []
    f = os.path.join(path, "cnames_active.js")
    if os.path.exists(f):
        for name, tgt in re.findall(r'"([a-z0-9_.-]+)"\s*:\s*"([^"]+)"', open(f, encoding="utf-8").read()):
            out.append((f"{name}.js.org" if name else "js.org", "", tgt))
    return out


def main():
    rows, report = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for repo, parent in REGISTRIES:
            d = os.path.join(tmp, repo.replace("/", "_"))
            if not clone(repo, d):
                report.append(f"{repo}: clone failed")
                continue
            got = from_dir(d, parent)
            report.append(f"{repo}: {len(got)}")
            rows += got
        d = os.path.join(tmp, "jsorg")
        if clone("js-org/js.org", d):
            got = jsorg(d)
            report.append(f"js-org/js.org: {len(got)}")
            rows += got
        else:
            report.append("js-org/js.org: clone failed")
    print("\n".join(report))
    uniq = {}
    for h, o, t in rows:
        uniq.setdefault(h, (o, t))
    if len(uniq) < 1000:
        sys.exit(f"only {len(uniq)} subdomains - keeping old list")
    with open(OUT, "w") as f:
        f.write("# hostname\towner\ttarget\n")
        for h in sorted(uniq):
            o, t = uniq[h]
            f.write(f"{h}\t{o}\t{t}\n")
    print(f"total: {len(uniq)}")


if __name__ == "__main__":
    main()
