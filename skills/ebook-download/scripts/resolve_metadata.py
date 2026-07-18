#!/usr/bin/env python3
"""resolve_metadata — turn a possibly-wrong/alternate/translated book title into
canonical title + author + ISBN, so libgen search can be anchored correctly.

Queries Open Library (English + international) and, when the title looks CJK,
Douban. Prints a JSON list of candidates ranked by relevance. The AGENT reads
this and decides which canonical title+author to feed to libgen_fetch.py.

Usage:
    python3 resolve_metadata.py "Some book title the user typed"
    python3 resolve_metadata.py --isbn 9781668012956
"""
import argparse, json, re, sys, urllib.parse, urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return json.loads(urllib.request.urlopen(req, timeout=15).read())


def openlibrary_search(q, limit=8):
    url = ("https://openlibrary.org/search.json?q="
           + urllib.parse.quote(q) + f"&limit={limit}"
           "&fields=title,subtitle,author_name,first_publish_year,isbn,language,edition_count")
    try:
        d = _get(url)
    except Exception as e:
        return {"error": repr(e), "results": []}
    out = []
    for x in d.get("docs", []):
        isbns = x.get("isbn", []) or []
        out.append({
            "title": x.get("title"),
            "subtitle": x.get("subtitle"),
            "author": x.get("author_name"),
            "year": x.get("first_publish_year"),
            "isbn": isbns[:3],
            "editions": x.get("edition_count"),
            "langs": x.get("language", [])[:5],
            # a libgen-friendly anchored query: distinctive title word + surname
            "suggested_libgen_query": _suggest(x),
        })
    return {"results": out}


def openlibrary_isbn(isbn):
    isbn = re.sub(r"[^0-9Xx]", "", isbn)
    try:
        d = _get(f"https://openlibrary.org/isbn/{isbn}.json")
    except Exception as e:
        return {"error": repr(e)}
    authors = []
    for a in d.get("authors", []):
        try:
            ad = _get("https://openlibrary.org" + a["key"] + ".json")
            authors.append(ad.get("name"))
        except Exception:
            pass
    return {
        "title": d.get("title"),
        "subtitle": d.get("subtitle"),
        "author": authors,
        "year": d.get("publish_date"),
        "publishers": d.get("publishers"),
        "pages": d.get("number_of_pages"),
        "isbn": isbn,
        "suggested_libgen_query": _suggest({"title": d.get("title"),
                                            "author_name": authors}),
    }


def douban(q):
    url = ("https://book.douban.com/j/subject_suggest?q="
           + urllib.parse.quote(q))
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, "Referer": "https://book.douban.com/"})
        d = json.loads(urllib.request.urlopen(req, timeout=10).read())
    except Exception as e:
        return {"error": repr(e), "results": []}
    return {"results": [{"title": x.get("title"), "author": x.get("author_name"),
                         "year": x.get("year"), "url": x.get("url"),
                         "id": x.get("id")} for x in d]}


def _suggest(x):
    """Build a precise libgen query: 1-2 distinctive title words + author surname."""
    title = (x.get("title") or "")
    authors = x.get("author_name") or x.get("author") or []
    surname = ""
    if authors:
        surname = str(authors[0]).split()[-1]
    STOP = {"the", "a", "an", "of", "and", "to", "in", "on", "for", "how",
            "your", "you", "rise", "power", "future", "inside", "story"}
    words = [w for w in re.findall(r"\w+", title) if w.lower() not in STOP and len(w) > 3]
    distinctive = words[:2]
    parts = distinctive + ([surname] if surname else [])
    return " ".join(parts).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?")
    ap.add_argument("--isbn")
    a = ap.parse_args()
    result = {}
    if a.isbn:
        result["by_isbn"] = openlibrary_isbn(a.isbn)
    if a.query:
        result["openlibrary"] = openlibrary_search(a.query)
        if re.search(r"[\u4e00-\u9fff\u3040-\u30ff]", a.query):
            result["douban"] = douban(a.query)
    if not result:
        print(json.dumps({"error": "provide a query or --isbn"}))
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
