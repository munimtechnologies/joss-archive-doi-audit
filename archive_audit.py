# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""JOSS archive-DOI audit 1.

Every paper in the Journal of Open Source Software (JOSS) names a software archive
(usually a Zenodo DOI) in its `software_archive` field. JOSS editors check each archive's
title and authors by hand at acceptance (openjournals/docs, editing.md). This script, for
every published JOSS paper:
  - parses the archive DOI;
  - reads its DataCite record (api.datacite.org); if DataCite has none, asks doi.org which
    registration agency holds it and whether the handle exists at all;
  - compares the record with the paper: code-repository links in relatedIdentifiers
    (with GitHub redirects resolved for renamed/moved repositories), software name in the
    record titles, JOSS author surnames among the record creators;
  - finds archive DOIs shared by papers of different repositories.
No API keys. Sources: joss.theoj.org/papers/published.json, api.datacite.org, doi.org,
github.com (redirects only).

Usage: python archive_audit.py --out-dir /out [--limit N]
"""
import argparse
import collections
import concurrent.futures
import csv
import datetime
import hashlib
import json
import os
import re
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

UA = "joss-archive-doi-audit/1.0 (MV2, Munim, Inc.; mv2@munimtech.com)"
JOSS_URL = "https://joss.theoj.org/papers/published.json?page={page}"
DATACITE_URL = "https://api.datacite.org/dois/{doi}"
RA_URL = "https://doi.org/ra/{doi}"
HANDLE_URL = "https://doi.org/api/handles/{doi}"
GITHUB_URL = "https://github.com/{path}"

DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'<>]+", re.IGNORECASE)
CODE_HOSTS = {"github.com", "bitbucket.org", "codeberg.org", "git.sr.ht", "sr.ht"}
STOP = {
    "python", "package", "packages", "library", "toolkit", "tool", "tools", "software",
    "analysis", "data", "open", "source", "framework", "with", "using", "based", "model",
    "models", "modeling", "modelling", "from", "into", "that", "this", "their", "julia",
    "implementation", "efficient", "fast", "simple", "system", "systems", "interface",
    "code", "version", "release", "toolbox", "platform", "suite", "module", "high",
    "performance", "scientific", "computing", "research", "application", "applications",
    "general", "purpose", "multi", "learning", "machine", "network", "networks", "tutorial",
    "journal", "paper", "joss", "submission", "accepted", "reviewed", "archive", "zenodo",
}
MAX_GITHUB_RESOLVE = 800


# ---------------------------------------------------------------- pure helpers
def parse_doi(s):
    """Lower-cased DOI found in a string (URL, 'doi:' form or bare), else None."""
    if not s or not isinstance(s, str):
        return None
    t = urllib.parse.unquote(s.strip())
    m = DOI_RE.search(t)
    if not m:
        return None
    d = m.group(0).rstrip(".,;)]/")
    return d.lower() if "/" in d else None


def repo_id(url):
    """'host/path' id of a code repository URL (lower case), else None.
    github.com ids are cut to owner/repo; GitLab '/-/' and '/tree/', '/blob/' tails are cut."""
    if not url or not isinstance(url, str):
        return None
    u = url.strip()
    if u.lower().startswith("git@"):
        rest = u[4:]
        if ":" not in rest:
            return None
        host, path = rest.split(":", 1)
        u = "https://" + host + "/" + path
    if "://" not in u:
        u = "https://" + u
    try:
        p = urllib.parse.urlparse(u)
        host = (p.hostname or "").lower()
    except ValueError:
        return None
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return None
    path = p.path
    cuts = ["/-/", "/tree/", "/blob/"]
    if host == "bitbucket.org":
        cuts.append("/src/")
    for cut in cuts:
        i = path.find(cut)
        if i >= 0:
            path = path[:i]
    parts = [x for x in path.split("/") if x]
    if host == "github.com":
        parts = parts[:2]
    if len(parts) < 2:
        return None
    if parts[-1].lower().endswith(".git"):
        parts[-1] = parts[-1][:-4]
    if not parts[-1]:
        return None
    return host + "/" + "/".join(parts).lower()


def ids_match(a, b):
    if not a or not b:
        return False
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def squash(s):
    t = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", t.lower())


def tokens(s):
    t = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode("ascii")
    return {w for w in re.findall(r"[a-z0-9]+", t.lower()) if len(w) >= 4 and w not in STOP}


def software_name(title):
    """The part of a JOSS title before the first ':' (often the software name), else ''."""
    if not title or ":" not in title:
        return ""
    return title.split(":", 1)[0].strip()


def author_hit(joss_authors, creators):
    """True if any JOSS author's last name is among the DataCite creators."""
    fams, joined = set(), []
    for c in creators or []:
        if not isinstance(c, dict):
            continue
        fn, nm = c.get("familyName"), c.get("name")
        if fn:
            fams.add(squash(fn))
        if nm:
            joined.append(squash(nm))
            if "," in nm:
                fams.add(squash(nm.split(",", 1)[0]))
    j = " ".join(joined)
    for a in joss_authors or []:
        ln = squash((a or {}).get("last_name") if isinstance(a, dict) else "")
        if not ln:
            continue
        if ln in fams:
            return True
        if len(ln) >= 4 and ln in j:
            return True
    return False


def code_links(related, extra_host=None):
    """Sorted repo ids of code-repository URLs among DataCite relatedIdentifiers."""
    out = set()
    for ri in related or []:
        if not isinstance(ri, dict):
            continue
        v = ri.get("relatedIdentifier")
        if not isinstance(v, str) or "/" not in v:
            continue
        low = v.strip().lower()
        if not ("://" in low or low.startswith(("github.com/", "www.github.com/", "gitlab", "git@"))):
            continue
        rid = repo_id(v)
        if not rid:
            continue
        host = rid.split("/", 1)[0]
        if host in CODE_HOSTS or "gitlab" in host or (extra_host and host == extra_host):
            out.add(rid)
    return sorted(out)


def is_concept(related):
    rts = {str((ri or {}).get("relationType", "")) for ri in related or [] if isinstance(ri, dict)}
    return "HasVersion" in rts and "IsVersionOf" not in rts


def link_status(own, links, resolver=None):
    """'no_code_link', 'match', 'match_after_redirect' or 'other_repo'."""
    if not links:
        return "no_code_link"
    if own and any(ids_match(own, l) for l in links):
        return "match"
    if own and resolver is not None:
        o2 = resolver(own) or own
        l2 = [resolver(l) or l for l in links]
        if any(ids_match(o2, l) for l in l2):
            return "match_after_redirect"
    return "other_repo"


def parse_ra(body):
    """(ra_name, state) from a doi.org/ra/<doi> JSON body."""
    try:
        js = json.loads(body.decode("utf-8"))
    except Exception:
        return "", "unparsed"
    if isinstance(js, list) and js and isinstance(js[0], dict):
        e = js[0]
        if e.get("RA"):
            return str(e["RA"]), "registered"
        st = str(e.get("status", "")).lower()
        if "does not exist" in st:
            return "", "does_not_exist"
        if "invalid" in st:
            return "", "invalid"
        return "", (st or "unknown").replace(" ", "_")
    return "", "unparsed"


def summarize_datacite(js):
    d = (js or {}).get("data") or {}
    at = d.get("attributes") or {}
    titles = [str(t.get("title", "")) for t in (at.get("titles") or []) if isinstance(t, dict)]
    creators = [{"name": c.get("name"), "familyName": c.get("familyName")}
                for c in (at.get("creators") or []) if isinstance(c, dict)]
    related = [{"relationType": ri.get("relationType"),
                "relatedIdentifierType": ri.get("relatedIdentifierType"),
                "relatedIdentifier": ri.get("relatedIdentifier")}
               for ri in (at.get("relatedIdentifiers") or []) if isinstance(ri, dict)]
    types = at.get("types") or {}
    return {"id": d.get("id"), "titles": titles, "creators": creators,
            "version": at.get("version"), "rtg": types.get("resourceTypeGeneral"),
            "url": at.get("url"), "state": at.get("state"), "created": at.get("created"),
            "publicationYear": at.get("publicationYear"), "related": related}


def iso_after(a, b):
    """True if ISO time a is later than ISO time b; None if either does not parse."""
    try:
        ta = datetime.datetime.fromisoformat(str(a).replace("Z", "+00:00"))
        tb = datetime.datetime.fromisoformat(str(b).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if ta.tzinfo is None:
        ta = ta.replace(tzinfo=datetime.timezone.utc)
    if tb.tzinfo is None:
        tb = tb.replace(tzinfo=datetime.timezone.utc)
    return ta > tb


def record_checks(paper, rec):
    """Name/author evidence that a DataCite record describes the paper's software."""
    titles = " ".join(rec.get("titles") or [])
    st = squash(titles)
    own = repo_id(paper.get("software_repository"))
    rname = squash(own.rsplit("/", 1)[-1]) if own else ""
    sw = squash(software_name(paper.get("title") or ""))
    return {
        "name_hit": bool(len(rname) >= 3 and rname in st),
        "sw_name_hit": bool(len(sw) >= 3 and sw in st),
        "token_hit": bool(tokens(paper.get("title") or "") & tokens(titles)),
        "author_hit": author_hit(paper.get("authors"), rec.get("creators")),
    }


# ---------------------------------------------------------------- network
class Pacer:
    def __init__(self, per_second):
        self.gap = 1.0 / per_second
        self.lock = threading.Lock()
        self.next = 0.0

    def wait(self):
        with self.lock:
            now = time.monotonic()
            t = max(now, self.next)
            self.next = t + self.gap
        d = t - time.monotonic()
        if d > 0:
            time.sleep(d)


PACE = {"joss": Pacer(3), "datacite": Pacer(6), "doi": Pacer(3), "github": Pacer(1)}


def http_get(url, pacer, accept=None, tries=5, timeout=40):
    """(status, body, final_url). 404/410 definitive; -1 = network failure."""
    delay = 5
    last = -1
    for _ in range(tries):
        pacer.wait()
        h = {"User-Agent": UA}
        if accept:
            h["Accept"] = accept
        req = urllib.request.Request(url, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read(), r.geturl()
        except urllib.error.HTTPError as e:
            last = e.code
            if e.code in (404, 410):
                try:
                    body = e.read()
                except Exception:
                    body = b""
                return e.code, body, url
            if e.code in (403, 429) or e.code >= 500:
                time.sleep(delay)
                delay = min(delay * 2, 120)
                continue
            return e.code, b"", url
        except Exception:
            time.sleep(delay)
            delay = min(delay * 2, 120)
    return last, b"", url


def fetch_joss(limit_pages=600):
    papers, seen = [], set()
    for page in range(1, limit_pages + 1):
        st, body, _ = http_get(JOSS_URL.format(page=page), PACE["joss"])
        if st == 404 and page > 1:
            break
        if st != 200:
            raise RuntimeError("JOSS page %d status %s" % (page, st))
        recs = json.loads(body.decode("utf-8"))
        if not recs:
            break
        new = [r for r in recs if r.get("doi") not in seen]
        if not new:
            break
        for r in new:
            seen.add(r.get("doi"))
        papers.extend(new)
    return papers


def q(doi):
    return urllib.parse.quote(doi, safe="/:")


def lookup(doi):
    out = {"dc_status": None, "rec": None, "ra": "", "ra_state": "", "handle_status": None}
    st, body, _ = http_get(DATACITE_URL.format(doi=q(doi)), PACE["datacite"],
                           accept="application/vnd.api+json")
    out["dc_status"] = st
    if st == 200:
        try:
            out["rec"] = summarize_datacite(json.loads(body.decode("utf-8")))
        except Exception:
            out["dc_status"] = "unparsed"
        return doi, out
    if st == 404:
        rst, rbody, _ = http_get(RA_URL.format(doi=q(doi)), PACE["doi"])
        out["ra"], out["ra_state"] = parse_ra(rbody) if rst == 200 else ("", "ra_http_%s" % rst)
        hst, _, _ = http_get(HANDLE_URL.format(doi=q(doi)), PACE["doi"])
        out["handle_status"] = hst
    return doi, out


class GitHubResolver:
    def __init__(self, cap=MAX_GITHUB_RESOLVE):
        self.cache, self.calls, self.cap, self.capped = {}, 0, cap, 0

    def __call__(self, rid):
        if not rid or not rid.startswith("github.com/"):
            return None
        if rid in self.cache:
            return self.cache[rid]
        if self.calls >= self.cap:
            self.capped += 1
            return None
        self.calls += 1
        st, _, final = http_get(GITHUB_URL.format(path=rid.split("/", 1)[1]), PACE["github"])
        res = repo_id(final) if st == 200 else None
        self.cache[rid] = res
        return res


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="/out")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    t0 = time.time()

    papers = fetch_joss()
    if a.limit:
        papers = papers[:a.limit]
    rows = []
    for p in papers:
        raw = p.get("software_archive") or ""
        adoi = parse_doi(raw)
        own = repo_id(p.get("software_repository"))
        rows.append({"joss_doi": (p.get("doi") or "").lower(), "title": p.get("title") or "",
                     "repo": p.get("software_repository") or "", "repo_id": own or "",
                     "published_at": p.get("published_at") or "", "state": p.get("state") or "",
                     "archive_raw": raw, "archive_doi": adoi or "",
                     "prefix": adoi.split("/", 1)[0] if adoi else "", "_paper": p})

    uniq = sorted({r["archive_doi"] for r in rows if r["archive_doi"]})
    info = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for doi, out in ex.map(lookup, uniq):
            info[doi] = out
    with open(os.path.join(a.out_dir, "datacite.jsonl"), "w", encoding="utf-8") as f:
        for doi in uniq:
            f.write(json.dumps({"doi": doi, **info[doi]}, ensure_ascii=False) + "\n")

    by_archive = collections.defaultdict(list)
    for r in rows:
        if r["archive_doi"]:
            by_archive[r["archive_doi"]].append(r)

    resolver = GitHubResolver()
    for r in rows:
        p = r.pop("_paper")
        r["suspect"] = []
        d = r["archive_doi"]
        if not d:
            r["dc_status"] = ""
            continue
        if d.startswith("10.21105/"):
            r["suspect"].append("S5_joss_doi_as_archive")
        grp = by_archive[d]
        others = [g for g in grp if g is not r]
        r["shared_n"] = len(others)
        r["shared_other_repo"] = ";".join(sorted({g["repo_id"] for g in others
                                                  if g["repo_id"] and r["repo_id"]
                                                  and not ids_match(g["repo_id"], r["repo_id"])}))
        r["shared_with"] = ";".join(g["joss_doi"] for g in others)
        if r["shared_other_repo"]:
            r["suspect"].append("S4_shared_archive_other_repo")
        x = info[d]
        r["dc_status"] = x["dc_status"]
        if x["dc_status"] == 404:
            r["ra"], r["ra_state"], r["handle_status"] = x["ra"], x["ra_state"], x["handle_status"]
            r["unregistered"] = (x["handle_status"] == 404
                                 and x["ra_state"] in ("does_not_exist", "invalid",
                                                       "ra_http_404"))
            if r["unregistered"]:
                r["suspect"].append("S3_unregistered_doi")
        rec = x["rec"]
        if x["dc_status"] != 200 or not rec:
            continue
        host = r["repo_id"].split("/", 1)[0] if r["repo_id"] else None
        links = code_links(rec["related"], extra_host=host)
        r["code_links"] = ";".join(links)
        r["link_status"] = link_status(r["repo_id"], links, resolver)
        r["rtg"] = rec.get("rtg") or ""
        r["dc_state"] = rec.get("state") or ""
        r["concept"] = is_concept(rec["related"])
        r["dc_version"] = rec.get("version") or ""
        r["dc_created"] = rec.get("created") or ""
        r["created_after_pub"] = iso_after(rec.get("created"), r["published_at"])
        r["dc_titles"] = " || ".join(rec.get("titles") or [])[:400]
        r["dc_creators"] = "; ".join((c.get("name") or c.get("familyName") or "")
                                     for c in rec.get("creators") or [])[:300]
        r.update(record_checks(p, rec))
        if r["link_status"] == "other_repo":
            r["suspect"].append("S1_links_other_repo")
        if r["link_status"] in ("no_code_link", "other_repo") and not (
                r["name_hit"] or r["sw_name_hit"] or r["token_hit"] or r["author_hit"]):
            r["suspect"].append("S2_no_name_or_author_overlap")
    for r in rows:
        r["suspect"] = ";".join(r["suspect"])

    fields = ["joss_doi", "title", "repo", "repo_id", "published_at", "state", "archive_raw",
              "archive_doi", "prefix", "dc_status", "ra", "ra_state", "handle_status",
              "unregistered", "rtg", "dc_state", "concept", "dc_version", "dc_created",
              "created_after_pub", "code_links", "link_status", "name_hit", "sw_name_hit",
              "token_hit", "author_hit", "shared_n", "shared_other_repo", "shared_with",
              "dc_titles", "dc_creators", "suspect"]

    def write(name, rs):
        with open(os.path.join(a.out_dir, name), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            for r in rs:
                w.writerow(r)

    write("papers.csv", rows)
    write("suspects.csv", [r for r in rows if r["suspect"]])
    write("no_doi.csv", [r for r in rows if not r["archive_doi"]])
    write("not_datacite.csv", [r for r in rows if r.get("dc_status") not in (200, "")])
    ok = [r for r in rows if r.get("link_status") in ("match", "match_after_redirect")
          and not r["suspect"]]
    ok_sample = sorted(ok, key=lambda r: hashlib.sha256(r["joss_doi"].encode()).hexdigest())[:30]
    write("ok_sample.csv", ok_sample)

    parsed = [r for r in rows if r["archive_doi"]]
    dc = [r for r in rows if r.get("dc_status") == 200]
    with_link = [r for r in dc if r.get("link_status") != "no_code_link"]
    matched = [r for r in with_link if r.get("link_status") in ("match", "match_after_redirect")]
    definitive = sum(1 for d in uniq if info[d]["dc_status"] == 200 or (
        info[d]["dc_status"] == 404 and info[d]["handle_status"] in (200, 404)))
    s_any = [r for r in rows if r["suspect"]]
    s_core = [r for r in rows if any(c in r["suspect"] for c in ("S1_", "S2_", "S4_"))]
    groups_other = sorted({r["archive_doi"] for r in rows if r.get("shared_other_repo")})
    groups_same = [d for d, g in by_archive.items() if len(g) > 1 and d not in set(groups_other)]

    def share(n, dnm):
        return round(n / dnm, 4) if dnm else None

    summary = {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runtime_s": round(time.time() - t0, 1),
        "joss_papers": len(rows),
        "with_archive_value": sum(1 for r in rows if r["archive_raw"]),
        "archive_doi_parsed": len(parsed),
        "archive_doi_parsed_share": share(len(parsed), len(rows)),
        "unique_archive_dois": len(uniq),
        "prefix_counts_top15": dict(collections.Counter(r["prefix"] for r in parsed).most_common(15)),
        "zenodo_share_of_parsed": share(sum(1 for r in parsed if r["prefix"] == "10.5281"), len(parsed)),
        "lookup_definitive_share": share(definitive, len(uniq)),
        "dc_status_counts_papers": dict(collections.Counter(str(r.get("dc_status")) for r in parsed)),
        "not_datacite_ra_counts": dict(collections.Counter(
            "%s|%s" % (r.get("ra_state"), r.get("ra")) for r in parsed if r.get("dc_status") == 404)),
        "unregistered_papers": sum(1 for r in rows if r.get("unregistered")),
        "unregistered_zenodo_papers": sum(1 for r in rows if r.get("unregistered")
                                          and r["prefix"] == "10.5281"),
        "datacite_papers": len(dc),
        "rtg_counts": dict(collections.Counter(r.get("rtg") for r in dc).most_common()),
        "software_share": share(sum(1 for r in dc if r.get("rtg") == "Software"), len(dc)),
        "dc_state_counts": dict(collections.Counter(r.get("dc_state") for r in dc)),
        "concept_share": share(sum(1 for r in dc if r.get("concept")), len(dc)),
        "code_link_share": share(len(with_link), len(dc)),
        "link_status_counts": dict(collections.Counter(r.get("link_status") for r in dc)),
        "own_repo_match_share_of_linked": share(len(matched), len(with_link)),
        "author_hit_share": share(sum(1 for r in dc if r.get("author_hit")), len(dc)),
        "created_after_pub": sum(1 for r in dc if r.get("created_after_pub") is True),
        "shared_archive_dois_other_repo": len(groups_other),
        "shared_archive_dois_same_repo": len(groups_same),
        "suspect_code_counts": dict(collections.Counter(
            c for r in s_any for c in r["suspect"].split(";") if c)),
        "suspect_papers_any": len(s_any),
        "suspect_papers_S1_S2_S4": len(s_core),
        "github_resolve_calls": resolver.calls,
        "github_resolve_capped": resolver.capped,
        "no_doi_papers": len(rows) - len(parsed),
    }
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
