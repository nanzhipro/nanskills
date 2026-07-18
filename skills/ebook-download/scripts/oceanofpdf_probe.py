#!/usr/bin/env python3
"""oceanofpdf_probe — search OceanofPDF and probe which formats a book offers,
WITHOUT launching Safari. Uses cloudscraper to read the WordPress `?s=` search
endpoint and each candidate's detail page, extracting the hidden download-form
`filename` values so you know up-front whether an EPUB even exists.

This turns OceanofPDF from "blindly open Safari and hope" into "confirm the
.epub form exists first, THEN run the Safari download flow only when it pays off".

Usage:
    python3 oceanofpdf_probe.py "As Bill Sees It"
    python3 oceanofpdf_probe.py "As Bill Sees It" --detail URL   # probe one page

Prints JSON. Exit 0 = at least one result, 3 = no results, 4 = cloudscraper missing.
"""
import argparse, json, re, sys, urllib.parse

try:
    import cloudscraper
except ImportError:
    print(json.dumps({"ok": False, "stage": "import",
                      "error": "cloudscraper missing — run: pip3 install cloudscraper"}))
    sys.exit(4)

BASE = "https://oceanofpdf.com"


def search(scraper, query):
    url = f"{BASE}/?s=" + urllib.parse.quote(query)
    r = scraper.get(url, timeout=30)
    hits = []
    for m in re.findall(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                        r.text, re.S):
        href, title = m[0], re.sub(r"<[^>]+>", "", m[1]).strip()
        if "oceanofpdf.com/authors/" in href:
            hits.append({"url": href, "title": title})
    return r.status_code, hits


def probe_formats(scraper, url):
    """Return the download-form filenames on a detail page (.epub/.pdf)."""
    r = scraper.get(url, timeout=30)
    files = re.findall(r'name="filename"[^>]*value="([^"]+)"', r.text)
    srv = re.findall(r'value="(srv\d+)"', r.text)
    exts = sorted({f.rsplit(".", 1)[-1].lower() for f in files if "." in f})
    return {"status": r.status_code, "filenames": files,
            "formats": exts, "has_epub": "epub" in exts,
            "has_pdf": "pdf" in exts, "srv": list(dict.fromkeys(srv))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--detail", help="probe a single detail-page URL instead of searching")
    ap.add_argument("--probe-all", action="store_true",
                    help="probe formats for every search hit (slower)")
    a = ap.parse_args()

    scraper = cloudscraper.create_scraper()

    if a.detail:
        info = probe_formats(scraper, a.detail)
        print(json.dumps({"ok": True, "stage": "probe", "url": a.detail, **info},
                         ensure_ascii=False, indent=2))
        return

    sc, hits = search(scraper, a.query)
    if not hits:
        print(json.dumps({"ok": False, "stage": "search", "status": sc,
                          "error": "no results", "query": a.query}))
        sys.exit(3)

    if a.probe_all:
        for h in hits:
            try:
                h.update(probe_formats(scraper, h["url"]))
            except Exception as e:
                h["error"] = repr(e)

    print(json.dumps({"ok": True, "stage": "search", "status": sc,
                      "count": len(hits), "results": hits},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
