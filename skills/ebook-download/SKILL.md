---
name: ebook-download
description: Find and download ebooks (EPUB-first, PDF fallback). A bundled script searches libgen.li, ranks candidates, downloads, and verifies from local terminal. When a title returns nothing, resolve the canonical title/author/ISBN via Open Library or Douban (bundled resolver) and retry — user-supplied titles are often alternate/marketing/wrong. Falls through Anna's Archive, OceanofPDF, and VK.com only when libgen has no match. Use when the user asks to find, search for, or download a specific book or ebook by title/author/ISBN.
version: 6.2.0
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [ebook, epub, pdf, download, libgen, oceanofpdf, annas-archive, openlibrary, books]
---

# Ebook Download

> ⚠️ **免责声明**：本 Skill 仅供学习研究使用，严禁用于违法违规行为。
> 因使用本 Skill 造成的任何损失，作者概不负责。完整声明见
> [仓库 README](../../README.md#%EF%B8%8F-免责声明)。

One goal: **the file lands on disk, verified, by the fastest, most stable path.**
EPUB first, PDF only after EPUB sources are exhausted. Fully automatic — never
ask "should I try the next source?"; the priority chain below IS the decision.

## Overview

The pipeline has three phases executed in strict order:

1. **Prepare** — detect network environment + system proxy, set env vars once
2. **Search** — cloudscraper (preferred) or browser-based libgen search
3. **Download** — background process through proxy for all files; foreground only for <10 MB

**The proxy is the critical enabler for GFW users.** Auto-detecting and
configuring it in Step 0 eliminates 80%+ of the failures documented in
historical sessions. The remaining 20% are CDN outages and libgen DB errors,
which are transient and handled via the fallback chain.

**Python runtime**: Step 0d dynamically discovers a Python with cloudscraper
installed — preferring Homebrew (OpenSSL) over system Python (LibreSSL) — and
exports `BOOK_PYTHON` for foreground use. Background commands include an inline
discovery snippet (env vars do NOT persist across foreground→background shell
boundaries). Foreground commands may use bare `python3` for readability.

**Path convention**: `{SKILL_DIR}` resolves to this skill's directory at
runtime. For foreground commands the agent may `cd` there and use relative
`scripts/...` paths; for background commands the absolute
`{SKILL_DIR}/scripts/...` form is required.

## Step 0 — Prepare the Network Environment (MANDATORY, runs first every time)

**This is not optional.** Before any search or download, run these diagnostics
and configure the environment. The download strategy is chosen based on results.

### 0a — Check direct network reachability

```bash
curl -s --max-time 8 -o /dev/null -w "%{http_code}" "https://libgen.li/" 2>&1
```

- `200` → terminal can reach libgen directly. Proxy is optional but may still help
  with download speed for large files.
- `000` or timeout → terminal is behind GFW. Proceed to 0b.

### 0b — Detect system proxy

```bash
networksetup -getsecurewebproxy Wi-Fi 2>&1
```

Parse the output: if `Enabled: Yes`, extract `Server` and `Port`. Typical Clash
Verge proxy is `127.0.0.1:7897`. Also check SOCKS:

```bash
scutil --proxy 2>&1 | grep -A2 SOCKS
```

### 0c — Configure environment

If a proxy is detected, set these variables **before any Python import**:

```python
import os
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7897'  # use detected host:port
os.environ['HTTP_PROXY']  = 'http://127.0.0.1:7897'
```

If NO proxy is detected and `curl` returned `000`: the terminal cannot reach
libgen at all. Skip to Step 1b (browser search) for discovery, then attempt
terminal cloudscraper download anyway (it may work via different TLS
fingerprinting — see pitfall #1). If cloudscraper download also fails, fall
through to Anna's / VK / OceanofPDF.

### 0d — Discover a working Python with cloudscraper (DYNAMIC, portable)

Find a Python that has cloudscraper installed, preferring Homebrew (OpenSSL) over
system Python (LibreSSL). Export `BOOK_PYTHON` — all subsequent steps use this
variable, never a hardcoded path:

```bash
for py in /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3 \
         /usr/local/bin/python3 /usr/bin/python3 python3; do
    if command -v "$py" >/dev/null 2>&1 && \
       $py -c "import cloudscraper; print($py, cloudscraper.__version__)" 2>/dev/null; then
        export BOOK_PYTHON="$py"
        break
    fi
done

# If none found, install cloudscraper for the first available Python.
if [ -z "$BOOK_PYTHON" ]; then
    for py in /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3 \
             /usr/local/bin/python3 /usr/bin/python3 python3; do
        if command -v "$py" >/dev/null 2>&1; then
            $py -m pip install --user cloudscraper && export BOOK_PYTHON="$py" && break
        fi
    done
fi

echo "BOOK_PYTHON=$BOOK_PYTHON"
```

The probe order prioritizes newer, OpenSSL-linked Pythons. On any machine (macOS
Apple Silicon, Intel, Linux), one of these paths will work. The exported variable
is available to foreground commands in this session. Background commands must
include their own inline discovery (see Step 2) — env vars do NOT cross the
foreground→background boundary.

### Strategy selection matrix

| curl result | proxy detected | Search | Download |
|---|---|---|---|
| 200 | — | cloudscraper (Step 1a) | foreground (<24MB) or background (≥24MB) |
| 000 | Yes | cloudscraper first, browser if exit 3 | background through proxy (mandatory for >10MB) |
| 000 | No | browser (Step 1b) | cloudscraper attempt → fallback chain |

## Step 1 — Search (find the book)

### Step 1a — cloudscraper search (preferred, try first always)

```bash
python3 scripts/libgen_fetch.py "Title AuthorSurname" --out ~/Downloads --search-only
```

Prefer `title keyword + author surname` over the full subtitle. The script
searches libgen.li, ranks candidates, and returns JSON. Exit codes:

- `0` → candidates found. Proceed to Step 2 (Download).
- `3` → nothing matched. Try browser search (Step 1b) before metadata resolution.
- `4` → cloudscraper missing. Run Step 0d.

Common flags: `--format epub` (default), `--lang English` (default), `--top N` (default 5).

### Step 1b — Browser-based libgen search (GFW fallback, CJK titles, very new books)

Use when Step 1a returns 0 results (exit 3), OR for CJK titles (pitfall #26),
OR for books published in the current year.

```
browser_navigate → https://libgen.li/
browser_type → search textbox with "Title keyword AuthorSurname"
browser_click → search button (🔍)
```

From the results, click a mirror link to reach `ads.php?md5=...`, then extract
the get.php URL:

```js
document.querySelector('a[href*="get.php"]').href
```

This returns `https://libgen.li/get.php?md5=MD5&key=KEY`. The key is
session-bound — use it immediately in Step 2. If libgen.li is slow, try
`libgen.vg` (same MD5 database).

Do NOT use `browser_navigate` on the get.php URL — it triggers a file download
with no HTML page, causing `net::ERR_ABORTED`. Extract the URL and download via
terminal cloudscraper instead.

## Step 2 — Download (get the file on disk)

> ⚠️ **BACKGROUND MODE**: ALWAYS use `$BOOK_PYTHON` (discovered in Step 0d).
> Bare `python3` may resolve to a different Python without cloudscraper in
> background shells. `$BOOK_PYTHON` is an absolute path that works everywhere.

### Run the script

The `libgen_fetch.py` script handles everything — search, streaming download
with progress (every 30s), proxy routing, and verification — in one command.
Remove the `--search-only` flag from Step 1a to proceed to download:

```bash
# Small files (<10 MB) or no proxy — foreground
python3 scripts/libgen_fetch.py "Title Author" --out ~/Downloads

# Behind proxy AND file ≥10 MB — background (mandatory)
# {SKILL_DIR} = the directory containing this SKILL.md (resolved at runtime)
terminal(background=true, notify_on_complete=true, command="""
# Auto-discover Python with cloudscraper (portable across machines).
BOOK_PYTHON=$(for py in /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3 \
                      /usr/local/bin/python3 /usr/bin/python3 python3; do
    command -v "$py" >/dev/null 2>&1 && \
    $py -c "import cloudscraper" 2>/dev/null && echo "$py" && break
done)
${BOOK_PYTHON:-python3} {SKILL_DIR}/scripts/libgen_fetch.py "Title Author" --out ~/Downloads
""")
```

The script:
- **Cache-first**: checks if a valid file already exists at the output path
  before downloading. Prints `Cached:` and skips the download entirely (~0.1s
  vs 14 minutes). Corrupt/stale files are auto-deleted and re-downloaded.
- Auto-detects proxy from `HTTPS_PROXY`/`HTTP_PROXY` env vars (set in Step 0c).
- Streams downloads with per-chunk progress: `  12.3MB / 180s = 70 KB/s`.
- Verifies EPUB (valid ZIP, title/creator from content.opf). Deletes stubs.
- Prints a final JSON result on success.

Exit codes: `0` = success, `2` = all attempts failed, `3` = nothing found,
`4` = cloudscraper missing.

### Strategy: foreground vs background

| Behind proxy? | File size | Method |
|---|---|---|
| No | Any | Foreground (fast, no proxy overhead) |
| Yes | <10 MB | Foreground `terminal(timeout=300)` |
| Yes | ≥10 MB | `terminal(background=true, notify_on_complete=true)` |

Proxy downloads are slow (~30-80 KB/s); 34 MB takes 7-19 minutes. Background
mode has no time limit; foreground caps at 600s (~25 MB at worst-case speed).

### Monitoring

While background download runs, poll for progress lines:

```bash
process(action='poll', session_id='proc_xxx')
```

Expect output like `  5.2MB / 120s = 44 KB/s` every ~30 seconds. If no new
output for >90 seconds and the file isn't on disk yet, the process may have
hung — kill it and retry (or check disk if the file already appeared).

### Post-download verification

After completion — OR if the process seems stuck with no progress output —
**check disk directly** before declaring failure:

```bash
ls -lh ~/Downloads/*{title keyword}*.epub
```

If the file exists with reasonable size, verify it:

```bash
python3 -c "
import zipfile, os
p = os.path.expanduser('~/Downloads/Book_Title.epub')
if zipfile.is_zipfile(p):
    z = zipfile.ZipFile(p)
    print(f'{len(z.namelist())} entries, {os.path.getsize(p)/1024/1024:.1f}MB')
    z.close()
"
```

If valid, report success and kill the background process — the file IS the
deliverable, not the process status (pitfall #32).

### Common download failure modes

| Error | Cause | Fix |
|---|---|---|
| HTTP 521/522 | libgen CDN down | Wait or fallback chain |
| HTTP 524 | Range resume rejected | Delete partial, fresh key, restart |
| `IncompleteRead` / `ChunkedEncodingError` | Proxy/CDN drop | Retry once, then fallback |
| Process "running" but no progress >90s | Script hung mid-transfer | Kill, retry; if file on disk, verify it |

## Step 3 — Fallback chain

Only when Step 2 fails (exit 2 or all download attempts exhausted).

Try in strict order. Bail after ~2 attempts per source.

| # | Source | EPUB? | How |
|---|--------|-------|-----|
| 1 | **Anna's Archive** | Yes | Try `.org` → `.se`. `.li`/`.gl` are JS-walled (pitfall #17). |
| 2 | **VK.com** | Yes | 1 cloudscraper + 1 browser attempt. <5 KB response = JS-walled. |
| 3 | **OceanofPDF** | Yes | Probe early via `oceanofpdf_probe.py --probe-all`. Manual Safari last resort. |
| 4 | **libgen PDF** | No | Accept only after all EPUB sources exhausted. |

**Anna's Archive** — `browser_navigate → https://annas-archive.org/md5/{MD5}`.
Fast unavailability check: cloudscraper the search endpoint. `.org`/`.se`
returning `ERR_CONNECTION_CLOSED` means unavailable here; skip to next source.

**VK.com** — `web_search: site:vk.com "{title}" {author} epub`. Extract
`vk.com/doc{uid}_{did}` links. Works best for pre-2024 books.

**OceanofPDF** — run `python3 scripts/oceanofpdf_probe.py "{title}" --probe-all`
early (in parallel with Step 1). The probe returns `has_epub` / `has_pdf` and
detail-page URLs. This is a MANUAL LAST RESORT: headless browser cannot pass
the Cloudflare iframe checkbox. Only offer manual Safari steps after ALL
automated channels (terminal cloudscraper, browser libgen, VK, Anna's) have
failed.

Detailed source URLs, dead mirrors, and per-source failure modes live in
`references/fallback-strategy.md` and `references/url-patterns.md`.

## Step 4 — Metadata resolution (when searches return nothing)

libgen groups editions under the book's **real** title. User-supplied titles are
frequently alternate, marketing, or translated. When all searches return 0,
resolve the canonical title + author + ISBN:

```bash
python3 scripts/resolve_metadata.py "Palantir Alex Karp"
python3 scripts/resolve_metadata.py --isbn 9781668012956
```

It queries Open Library (and Douban for CJK titles) and returns a
`suggested_libgen_query`. Re-run Step 1 with that query.

> Worked example: "Inside Palantir…" → 0 hits → resolved to "The Philosopher in
> the Valley" by Steinberger → `libgen_fetch.py "Philosopher Valley Steinberger"`
> downloaded 1.1 MB EPUB. See `references/case-study-inside-palantir.md`.

Skip metadata resolution for books published in the current year — Open Library
won't have them. Go straight to browser search (Step 1b).

## Step 5 — Multi-book / edition-constrained requests

1. **Triage first, download second.** Run `--search-only` across ALL titles.
2. **EPUB-first-PDF-fallback applies PER TITLE.**
3. **Report a per-book table** (title / format / size / edition-year / source).

## Pitfalls

1. **Always run Step 0 first.** Auto-detecting the proxy and setting env vars
   eliminates the most common failure class (GFW blocks). Never skip network
   preparation — it costs 5 seconds and saves 30+ minutes of debugging.
2. **Don't reach for the browser on libgen until proxy-configured cloudscraper
   fails.** With proxy configured, cloudscraper handles both search and download
   reliably. Only use browser search (Step 1b) when cloudscraper returns exit 3
   or for CJK titles.
3. **libgen.li download key is session-bound** — each `ads.php` visit mints a
   fresh key; never reuse an old one. The bundled script handles this.
4. **Size beats format label** — prefer the largest real file; a tiny EPUB is
   often a stub. The script's ranking already does this.
5. **Verify every file** — a saved 404/HTML page is not a book. The script
   checks EPUB = valid ZIP with entries, PDF = `%PDF-` magic. If verify fails it
   deletes the file and tries the next candidate.
6. **HTTP/2 5MB cutoff (only if you hand-roll curl)** — libgen over HTTP/2 cuts
   off at 5MB; use `curl --http1.1`. cloudscraper avoids this entirely.
7. **Large files through proxy** — downloads run at ~30-80 KB/s. The script now
   uses streaming with per-chunk progress (printed every 30s). Background mode
   is still mandatory for ≥10 MB behind proxy because foreground caps at 600s.
   Cap at 2 attempts per file; if both fail, move to fallback chain.
8. **HTTP Range resume with libgen get.php returns 524** — Cloudflare rejects
   Range requests on the CDN. Each get.php key is session-bound; you cannot
   resume a download started with one key using another. Delete the partial
   file, get a fresh key from the browser, and restart from scratch.
9. **Safari / computer_use cannot download libgen get.php links** — `open -a
   Safari` with a get.php URL opens a blank tab. `computer_use` driving Safari
   is equally ineffective. The only reliable path is terminal cloudscraper.
10. **IPFS / mirror links are dead** — Cloudflare-IPFS, ipfs.io, Pinata,
    randombook.org, libgen.pw all return HTML, not files. Don't click them.
11. **Z-Library domains are all dead** — cap at 2 attempts, move on.
12. **Wrong / alternate / marketing titles are common** — if a title search
    returns 0, do NOT conclude the book is unavailable. Run Step 4
    (`resolve_metadata.py`) to find the canonical title + author, then retry.
13. **Very new translations** — Chinese/other translations published within weeks
    rarely have scans yet. Fall back to the English original.
14. **Don't let the script degrade to a single common word** — the ladder is
    capped at full → head → head-short (≤6 tokens) → stopwords-dropped. It
    never degrades to a single-token query.
15. **Long subtitles kill libgen matches** — prefer `title keyword + author
    surname` over the full subtitle. `--search-only` helps preview results.
16. **OceanofPDF `file` reports "Zip archive" not "EPUB document"** — cosmetic
    (mimetype not first in ZIP); the file is valid.
17. **Different MD5s across sources** — Anna's and libgen keep different
    digitizations of the same title; a mismatch is not a failure.
18. **Run the fetcher via `terminal`, not `execute_code`** — the `execute_code`
    sandbox uses an isolated Python that does NOT see `pip3 install`ed packages.
    Always invoke bundled scripts through `terminal`.
19. **`defaults write com.apple.Safari …` fails on macOS 26** — the container
    sandbox rejects it. The `AllowJavaScriptFromAppleEvents` setting for
    OceanofPDF may already be enabled, or must be toggled manually.
20. **Anna's Archive `.li` and `.gl` serve JS challenges** — when `.org`/`.se`
    are unreachable, `.li`/`.gl` return ~10-13 KB JS anti-bot pages. Treat as
    unavailable and move to next source.
21. **Decades-old canon rarely has a "new edition" EPUB in free circulation** —
    take the best available format and state the limitation clearly.
22. **Headless browser CANNOT bypass OceanofPDF Cloudflare iframe checkbox** —
    OceanofPDF is MANUAL LAST RESORT only. Exhaust all automated channels first.
23. **Background terminal cloudscraper** — cloudscraper is importable in
    background processes when using `$BOOK_PYTHON` (discovered in Step 0d).
    The earlier `ModuleNotFoundError` was from using bare `python3` which
    resolved to a different Python without cloudscraper.
24. **VK.com is increasingly anti-bot** — cloudscraper returns minimal HTML with
    no doc links. Give it ONE cloudscraper + ONE browser attempt; if <5 KB or no
    `doc` IDs, mark unavailable and move on.
25. **Browser libgen can find results terminal cloudscraper misses** — happens
    with CJK titles and very new English books. After exit 3, try browser search
    with simplified keywords BEFORE Step 4 resolution.
26. **Run the OceanofPDF probe in parallel during Step 1** — `oceanofpdf_probe.py`
    is fast (~3s) and independent of libgen. Launch alongside first search.
27. **`browser_navigate` to `get.php` returns `net::ERR_ABORTED`** — NOT a
    failure. The browser triggers an immediate file download with no HTML page.
    Extract the URL via `browser_console` and download via terminal cloudscraper.
28. **libgen "MySQL server has gone away" (database 9306) is shared across ALL
    frontend domains** — wait 1-2 minutes, retry `libgen_fetch.py --search-only`;
    the script's API layer often recovers before the browser frontend.
29. **HTTP Range resume with libgen get.php returns 524** — (reinforced from #8).
    Delete partial, fresh key, restart from scratch.
30. **Background process `PATH` may differ from foreground** — always use
    `$BOOK_PYTHON` (discovered in Step 0d) in background download commands.
    Bare `python3` may resolve to system Python or a different installation
    without cloudscraper.
31. **`export` in foreground does NOT reach background shells** — environment
    variables set via `export` in a foreground `terminal()` call are invisible
    to subsequent `terminal(background=true)` calls. The only reliable pattern
    is inline discovery inside the background command itself (as shown in
    Step 2). Do not assume `$BOOK_PYTHON` or proxy env vars carry over. Tested
    and confirmed 2026-07: `echo $BOOK_PYTHON` in background → empty string.
32. **Process stays "running" after file written** — streaming with proper
    `r.close()` in the updated script reduces this significantly, but network
    quirks can still cause post-write hangs. Don't wait indefinitely for process
    exit. Periodically check disk: if the file exists with reasonable size,
    verify it immediately. If valid, kill the process and report success — the
    file IS the deliverable, not the process status.
33. **`ChunkedEncodingError` almost always resolves on retry** — a single proxy
    glitch mid-transfer drops the connection. The script deletes the partial
    file automatically and exits 2. Retry once immediately (same query, same
    `--out`); the new key + fresh connection succeeds >90% of the time. Don't
    skip to the fallback chain after one `ChunkedEncodingError`.
34. **Partial files are auto-cleaned on failure** — if the script exits 2,
    there is no partial `.epub` left on disk (the `download()` function writes
    to the target path only on success). No manual cleanup needed before retry.
35. **Verify rejects partials with two thresholds** — files <100 KB are
    rejected outright (stubs). Valid ZIP files with <10 entries are also
    rejected (partial downloads may have a few ZIP headers but no real content).
    These guards prevent the cache check from accepting incomplete files.
36. **Cache is filename-based, not content-based** — the script derives the
    output filename from the query string (`re.sub(r"[^\w\- ]", "", query)`).
    Re-running with the same query hits cache; a different query for the same
    book (e.g. "Steve Jobs Exile" vs "Steve Jobs NeXT") produces a different
    filename and won't find the cached file. Use consistent query strings
    across sessions for cache reuse.

## Verification

The bundled script self-verifies. When downloading manually, confirm:
1. Size is reasonable (>100 KB; EPUB typically 0.5-5 MB, PDF 1-15 MB).
2. `file path` (EPUB → "EPUB document"/"Zip archive"; PDF → "PDF document").
3. EPUB is a valid ZIP: `python3 -c "import zipfile; print(len(zipfile.ZipFile('P').namelist()))"`.
4. Optionally parse `content.opf` `<dc:title>`/`<dc:creator>` to confirm identity.

Report: filename, format, size, language, source, and save path.

## When All Sources Fail — User Escalation Template

When every automated path is exhausted, provide a concrete, copy-paste-ready
manual download guide. Include:

1. **What was found** — book title, author, confirmed format, MD5, file size, source.
2. **Why automation failed** — one sentence per attempted source with the specific failure mode.
3. **The exact manual steps** — self-contained numbered list.

### Template

```
## {Book Title} by {Author} — Confirmed Available, Manual Download Required

**Confirmed**: {Source} has {format}, {size}.

**Why automation failed**:
- libgen: {specific failure}
- Anna's Archive: {specific failure}
- OceanofPDF: Cloudflare iframe checkbox cannot be passed by headless browser

**Manual download (10 seconds)**:

1. Open in your browser: `{detail-page URL}`
2. Wait ~5 seconds for Cloudflare to verify automatically (if a checkbox appears, click "Verify you are human")
3. Find the EPUB download button and click it
4. The file saves automatically to `~/Downloads/`, prefixed `_OceanofPDF.com_`
```

If the ONLY available source is libgen (no OceanofPDF listing), include the
libgen MD5 link: `https://libgen.li/ads.php?md5={MD5}` (or `.vg` as fallback),
and instruct the user to click the "GET" link.