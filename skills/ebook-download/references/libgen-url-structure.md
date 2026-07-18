# libgen.li URL Structure — Complete Reference

Base URL: `https://libgen.li`

## Search — `/index.php`

```
/index.php?req=<query>&columns[]=t&columns[]=a&columns[]=s&columns[]=y&columns[]=p&columns[]=i&objects[]=f&objects[]=e&objects[]=s&objects[]=a&objects[]=p&objects[]=w&topics[]=l&topics[]=c&topics[]=f&topics[]=a&topics[]=m&topics[]=r&topics[]=s&curtab=f
```

### `columns` — Which metadata fields to display
| Code | Field |
|------|-------|
| `t` | Title |
| `a` | Author(s) |
| `s` | Series |
| `y` | Year |
| `p` | Publisher |
| `i` | ISBN |

### `objects` — What entity types to search
| Code | Entity |
|------|--------|
| `f` | Files (the actual downloadable items) |
| `e` | Editions (bibliographic records) |
| `s` | Series |
| `a` | Authors |
| `p` | Publishers |
| `w` | Works (abstract work grouping multiple editions) |

### `topics` — Which collections to search
| Code | Collection |
|------|-----------|
| `l` | Libgen (non-fiction / main) |
| `c` | Comics |
| `f` | Fiction |
| `a` | Scientific Articles |
| `m` | Magazines |
| `r` | Fiction (Russian) |
| `s` | Standards |

### Other parameters
- `curtab=f` — show Files tab by default (skip Editions/Series/Authors tabs)
- Phrase search: wrap query in `%22` (URL-encoded `"`)
- `res=25` — results per page (25 default, max 100)
- `view=simple` — simple view without covers

## File Info — `/file.php`

```
/file.php?md5=<MD5_HASH>
```

Returns: file metadata (size, format, hashes), edition links, mirror links (Libgen, Randombook, Anna's Archive, libgen.pw, TOR).

## Edition — `/edition.php`

```
/edition.php?id=<EDITION_ID>
```

Shows "Files (1)" table with `ads.php?md5=...` download gateway link. Also contains TOR direct download URL.

## Ads Gateway — `/ads.php`

```
/ads.php?md5=<MD5_HASH>
```

HTML page that embeds the session-scoped download URL:
```
get.php?md5=<MD5>&key=<SESSION_KEY>
```

The `key` parameter is random per session. Regex: `get\.php\?md5=[a-f0-9]+&key=([A-Z0-9]+)`

## Download — `/get.php`

```
/get.php?md5=<MD5>&key=<SESSION_KEY>
```

- Returns file as `application/octet-stream`
- `Content-Disposition: attachment; filename="..."`
- **Requires** `Referer: https://libgen.li/ads.php?md5=<MD5>`
- Inner workings: the key is validated server-side against the session; no key = no file

## ID Conventions

| Type | Example | Format |
|------|---------|--------|
| MD5 | `0c42d481b89947c9c34453e5e886eb73` | 32 hex chars, lowercase |
| Edition ID | `151349954` | Numeric |
| File ID | `108285458` | Numeric (used in `download.php?id=...` — returns 404, do not use) |

## Mirror Domains (from file.php)

| Domain | Reality |
|--------|---------|
| `randombook.org/book/<MD5>` | Nuxt SPA, no direct download possible |
| `libgen.pw/book/<MD5>` | Nuxt SPA, no direct download possible |
| Anna's Archive | Frequently blocked |
| TOR: `libgenfrialc7tguyjywa36vtrdcplwpxaw43h6o63dmmwhvavo5rqqd.onion` | Direct download via `/LG/<DIR>/<MD5>/<FILENAME>` — requires Tor |

## Typical File Sizes

| Format | Typical Range |
|--------|---------------|
| EPUB | 0.5–5 MB (most: 1–3 MB) |
| PDF | 1–15 MB (scanned: 10–50 MB) |
| Fiction EPUB | 0.3–2 MB |
| Academic PDF | 2–30 MB |

If downloaded file is <100KB: likely an HTML error page saved with wrong extension. Verify with `file` command.
