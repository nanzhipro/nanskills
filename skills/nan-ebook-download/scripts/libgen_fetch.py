#!/usr/bin/env python3
"""libgen_fetch — search, rank, download, verify an ebook from libgen.li in one shot.

Usage:
    python3 libgen_fetch.py "Title Author" [--format epub] [--lang English]
                            [--out ~/Downloads] [--search-only]

Prints a JSON object to stdout describing the result.
Exit code 0 = file on disk, 2 = found but download failed, 3 = nothing found.
"""
import argparse, json, os, re, sys, time

try:
    import cloudscraper
except ImportError:
    print(json.dumps({"ok": False, "stage": "import",
                      "error": "cloudscraper missing — run: pip3 install cloudscraper"}))
    sys.exit(4)

BASE = "https://libgen.li"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")
FORMAT_RANK = {"epub": 0, "azw3": 1, "mobi": 2, "fb2": 3, "pdf": 4, "djvu": 5}


def size_to_bytes(s):
    m = re.search(r"(\d+(?:\.\d+)?)\s*(B|kB|KB|MB|GB)", s)
    if not m:
        return 0
    try:
        n = float(m.group(1))
    except ValueError:
        return 0
    u = m.group(2).lower()
    return int(n * {"b": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3}[u])


def search(scraper, query, retries=3):
    # libgen.bz uses a different search query shape than libgen.li.
    if "libgen.bz" in BASE:
        url = (f"{BASE}/index.php?req={query.replace(' ', '+')}"
               "&open=0&res=100&view=simple&phrase=1&column=def")
    else:
        url = (f"{BASE}/index.php?req={query.replace(' ', '+')}"
               "&columns[]=t&columns[]=a&columns[]=s&columns[]=y&columns[]=p&columns[]=i"
               "&objects[]=f&topics[]=l&topics[]=f&res=100&curtab=f")
    last = None
    for i in range(retries):
        try:
            r = scraper.get(url, timeout=45)
            if r.status_code == 200 and "tablelibgen" in r.text:
                return r.text
            last = f"status {r.status_code}"
        except Exception as e:
            last = repr(e)
        time.sleep(0.6)
    raise RuntimeError(f"search failed: {last}")


# Only true grammar stopwords — nouns/verbs that carry semantic weight in book
# titles (life, story, power, world, etc.) are intentionally NOT here so they
# survive degradation and keep the search precise.
STOPWORDS = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "for",
             "how", "is", "are", "your", "you", "with", "through"}


def build_query_ladder(query):
    """Return a short, precise ladder: full → head → head-short → stopwords.

    Four rungs, no guessing.  Rungs 2-3 progressively shorten the query to
    account for subtitles and noise words the user may have included alongside
    the canonical title.  "Head" snips at the first colon/comma/semicolon/dash;
    "head-short" caps the head at 6 tokens — most canonical titles are ≤6 words,
    and libgen's title-column index often rejects queries that are too long.
    Earlier versions degraded to a single longest-token, which pulled 100
    unrelated books (verified: "Secretive" → North-Korea memoirs).  Fuzzy
    resolution of alternate/marketing/wrong titles is the AGENT's job via
    metadata APIs; when the script returns 0, the agent resolves the canonical
    title+author and re-runs.
    """
    ladder = [query]

    # Rung 2: head — cut at the first subtitle separator.
    head = re.split(r'[,:;—–-]', query, maxsplit=1)[0].strip()
    if head and head.lower() != query.lower():
        ladder.append(head)

    # Rung 3: head-short — cap the head at 6 tokens (most titles ≤6 words).
    head_tokens = head.split()
    if len(head_tokens) > 6:
        head_short = " ".join(head_tokens[:6])
        if head_short.lower() not in {q.lower() for q in ladder}:
            ladder.append(head_short)

    # Rung 4: full query with stopwords dropped.
    tokens = re.findall(r"\w+", query)
    kept = [t for t in tokens if t.lower() not in STOPWORDS and len(t) > 2]
    stripped = " ".join(kept)
    if stripped and stripped.lower() != query.lower():
        ladder.append(stripped)

    seen, out = set(), []
    for q in ladder:
        if q and q.lower() not in seen:
            seen.add(q.lower()); out.append(q)
    return out


def search_with_degradation(scraper, query):
    """Try each rung of the query ladder until one returns parseable rows.
    Returns (rows, used_query, attempts)."""
    attempts = []
    for q in build_query_ladder(query):
        try:
            html = search(scraper, q)
        except Exception as e:
            attempts.append({"query": q, "error": str(e)})
            continue
        rows = parse_rows(html)
        attempts.append({"query": q, "rows": len(rows)})
        if rows:
            return rows, q, attempts
    return [], None, attempts


def parse_rows(html):
    ti = html.find('id="tablelibgen"')
    seg = html[ti:] if ti > 0 else html
    end = seg.find("</table>")
    if end > 0:
        seg = seg[:end + 8]
    rows = re.split(r"<tr[^>]*>", seg)
    out = []
    for row in rows[1:]:
        md = re.search(r"md5=([a-fA-F0-9]{32})", row)
        if not md:
            continue
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        texts = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip() for c in cells]
        joined = " ".join(texts)
        # Resilient field detection (independent of exact column order).
        ext = ""
        for t in texts:
            if t.lower() in FORMAT_RANK:
                ext = t.lower(); break
        size = 0
        for t in texts:
            b = size_to_bytes(t)
            if b:
                size = max(size, b)
        lang = ""
        for t in texts:
            if t in ("English", "Chinese", "German", "French", "Spanish",
                     "Russian", "Japanese", "Italian"):
                lang = t; break
        year = ""
        ym = re.search(r"\b(19|20)\d{2}\b", joined)
        if ym:
            year = ym.group(0)
        # Title = first anchor text after the edition link in cell 0.
        title = texts[0][:200] if texts else ""
        out.append({"md5": md.group(1), "ext": ext, "size": size,
                    "lang": lang, "year": year, "raw": joined[:300]})
    return out


def rank(rows, query, want_format, want_lang):
    q_tokens = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]

    def score(r):
        # relevance: how many query tokens appear in the row text
        rl = r["raw"].lower()
        rel = sum(1 for t in q_tokens if t in rl)
        fmt = FORMAT_RANK.get(r["ext"], 9)
        if want_format:
            fmt = 0 if r["ext"] == want_format else fmt + 10
        lang_ok = 0 if (not want_lang or r["lang"] == want_lang) else 1
        stub = 1 if r["size"] and r["size"] < 50 * 1024 else 0
        # sort key: more relevant, preferred lang, preferred format,
        # not-a-stub, then larger file
        return (-rel, lang_ok, fmt, stub, -r["size"])

    return sorted(rows, key=score)


def get_download_key(scraper, md5, retries=3):
    for i in range(retries):
        try:
            r = scraper.get(f"{BASE}/ads.php?md5={md5}", timeout=45)
            m = re.search(r"get\.php\?md5=[a-fA-F0-9]{32}&key=([A-Za-z0-9]+)", r.text)
            if m:
                return m.group(0)
        except Exception:
            pass
        time.sleep(0.6)
    return None


def download(scraper, md5, out_path):
    link = get_download_key(scraper, md5)
    if not link:
        return False, "no download key from ads.php"
    url = f"{BASE}/{link}"
    headers = {"Referer": f"{BASE}/ads.php?md5={md5}", "User-Agent": UA}
    try:
        # Streaming with separate connect (30s) and read (600s) timeouts.
        # 600s = 10 min covers ~34 MB at ~57 KB/s through a proxy.
        r = scraper.get(url, headers=headers, timeout=(30, 600),
                        allow_redirects=True, stream=True)
    except Exception as e:
        return False, f"download error: {e!r}"
    if r.status_code != 200:
        r.close()
        return False, f"bad response: status {r.status_code}"

    total = 0
    start = time.time()
    last_report = 0
    try:
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=262144):
                if chunk:
                    f.write(chunk)
                    total += len(chunk)
                    now = time.monotonic()
                    if now - last_report > 30:
                        elapsed = time.time() - start
                        speed = total / 1024 / elapsed if elapsed > 0 else 0
                        print(f"  {total/1024/1024:.1f}MB / {elapsed:.0f}s"
                              f" = {speed:.0f} KB/s", flush=True)
                        last_report = now
    except Exception as e:
        r.close()
        # Clean up partial file so cache check doesn't mistake it for valid.
        if os.path.exists(out_path):
            os.remove(out_path)
        return False, f"write error after {total} bytes: {e!r}"
    finally:
        r.close()

    if total < 1024:
        if os.path.exists(out_path):
            os.remove(out_path)
        return False, f"file too small: {total} bytes"
    elapsed = time.time() - start
    print(f"  Done: {total/1024/1024:.1f}MB in {elapsed:.0f}s"
          f" ({total/1024/elapsed:.0f} KB/s)", flush=True)
    return True, total


def verify(path):
    import zipfile
    info = {"bytes": os.path.getsize(path)}
    # Reject files smaller than 100 KB — they're almost certainly stubs.
    if info["bytes"] < 100 * 1024:
        return False, info
    if path.lower().endswith(".epub"):
        if not zipfile.is_zipfile(path):
            return False, info
        z = zipfile.ZipFile(path)
        entries = z.namelist()
        info["entries"] = len(entries)
        # Require at least 10 entries — partial downloads have < 5.
        if len(entries) < 10:
            z.close()
            return False, info
        opf = [n for n in entries if n.endswith(".opf")]
        if opf:
            data = z.read(opf[0]).decode("utf-8", "ignore")
            for tag in ("title", "creator"):
                mm = re.search(rf"<dc:{tag}[^>]*>(.*?)</dc:{tag}>", data)
                if mm:
                    info[tag] = mm.group(1)
        return info["entries"] > 0, info
    if path.lower().endswith(".pdf"):
        with open(path, "rb") as f:
            head = f.read(5)
        return head == b"%PDF-", info
    return True, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--format", default="epub", help="preferred format (epub/pdf/...)")
    ap.add_argument("--lang", default="English")
    ap.add_argument("--out", default="~/Downloads")
    ap.add_argument("--search-only", action="store_true")
    ap.add_argument("--top", type=int, default=5, help="candidates to try in order")
    ap.add_argument("--base", default="https://libgen.li",
                    help="libgen mirror base URL (use https://libgen.bz when "
                         "libgen.li is blocked by the network/proxy)")
    a = ap.parse_args()

    global BASE
    BASE = a.base.rstrip("/")

    # Respect proxy env vars before any network call.
    # cloudscraper's requests.Session reads HTTP_PROXY/HTTPS_PROXY from
    # os.environ at request time, so setting them here (post-import) works.
    for var in ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy",
                "ALL_PROXY", "all_proxy"):
        val = os.environ.get(var)
        if val:
            os.environ.setdefault("HTTPS_PROXY", val)
            os.environ.setdefault("HTTP_PROXY", val)
            break

    scraper = cloudscraper.create_scraper()
    try:
        rows, used_query, attempts = search_with_degradation(scraper, a.query)
    except Exception as e:
        print(json.dumps({"ok": False, "stage": "search", "error": str(e)}))
        sys.exit(3)

    if not rows:
        print(json.dumps({"ok": False, "stage": "parse",
                          "error": "no results", "query": a.query,
                          "attempts": attempts}))
        sys.exit(3)

    # Rank against the query that actually matched (better token overlap).
    ranked = rank(rows, used_query or a.query,
                  a.format.lower() if a.format else "", a.lang)
    top = ranked[:a.top]

    if a.search_only:
        print(json.dumps({"ok": True, "stage": "search",
                          "used_query": used_query, "attempts": attempts,
                          "candidates": top}, ensure_ascii=False, indent=2))
        return

    outdir = os.path.expanduser(a.out)
    os.makedirs(outdir, exist_ok=True)
    tried = []
    for cand in top:
        ext = cand["ext"] or a.format or "epub"
        safe = re.sub(r"[^\w\- ]", "", a.query)[:80].strip() or "book"
        out_path = os.path.join(outdir, f"{safe}.{ext}")

        # Cache check — skip download if a valid file already exists.
        if os.path.exists(out_path):
            vok, vinfo = verify(out_path)
            if vok:
                print(f"  Cached: {out_path} "
                      f"({vinfo.get('bytes', 0)/1024/1024:.1f}MB, "
                      f"{vinfo.get('entries', '?')} entries)", flush=True)
                print(json.dumps({"ok": True, "stage": "cached",
                                  "path": out_path, "verify": vinfo,
                                  "md5": cand["md5"], "ext": ext,
                                  "candidate": cand, "tried": tried},
                                 ensure_ascii=False, indent=2))
                return
            # File exists but is invalid (stub / corrupt) — delete and re-download.
            print(f"  Stale file, re-downloading: {out_path}", flush=True)
            os.remove(out_path)

        ok, res = download(scraper, cand["md5"], out_path)
        tried.append({"md5": cand["md5"], "ext": ext, "ok": ok, "detail": res})
        if ok:
            vok, vinfo = verify(out_path)
            if not vok:
                os.remove(out_path)
                tried[-1]["ok"] = False
                tried[-1]["detail"] = f"verify failed: {vinfo}"
                continue
            print(json.dumps({"ok": True, "stage": "done", "path": out_path,
                              "verify": vinfo, "md5": cand["md5"], "ext": ext,
                              "candidate": cand, "tried": tried},
                             ensure_ascii=False, indent=2))
            return
    print(json.dumps({"ok": False, "stage": "download",
                      "error": "all candidates failed", "tried": tried},
                     ensure_ascii=False, indent=2))
    sys.exit(2)


if __name__ == "__main__":
    main()
