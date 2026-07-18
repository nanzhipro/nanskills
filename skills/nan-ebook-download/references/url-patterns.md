# URL Patterns — Known Working and Broken

Every URL pattern tested across two real download sessions. **Only use patterns marked ✅.**

## libgen.li Gateway (Primary)

| URL Pattern | Status | Notes |
|---|---|---|
| `libgen.li/get.php?md5=X&key=Y` | ✅ | Primary download. Requires key from ads.php. Always set Referer. |
| `libgen.li/ads.php?md5=X` | ✅ | Gateway page that exposes the session download key. |
| `libgen.li/file.php?md5=X` | ✅ | File info page with mirror links and edition references. |
| `libgen.li/index.php?req=...&curtab=f` | ✅ | Search page. Use `curtab=f` for files-only results. |

## Direct Download Sources (Fallback)

| URL Pattern | Status | Notes |
|---|---|---|
| `vk.com/doc{uid}_{did}?hash=X&api=1&no_preview=1` | ✅ | VK document direct download. No Referer, no key. Content-Type: `application/octet-stream`. Found via `site:vk.com` web_search. **#1 fallback for popular English books.** |
| `dokumen.pub/{slug}-{isbn}.html` | ⚠️ | PDF-only in tested cases. May require password. |

## Broken — Never Use

| URL Pattern | Failure Mode |
|---|---|
| `library.lol/main/X` | SSL EOF / 404 |
| `download.library.lol/main/X` | SSL EOF |
| `libgen.is/download/book/X` | SSL EOF — connection killed mid-handshake |
| `libgen.gs/*`, `libgen.st/*` | SSL EOF |
| `cdn.booksdl.org/main/X` | SSL EOF |
| `libgen.rocks/get.php?md5=X` | SSL cert verification failure |
| `randombook.org/book/X` | Nuxt SPA — `downloadEndpointURL` is empty string |
| `libgen.pw/book/X` | Nuxt SPA — same empty config |
| `cdn.bookey.app/files/pdf/*` | 403 Forbidden |
| `tiinyurl.cc/*` | 403 Forbidden |

## Z-Library — All Domains Dead

| Domain | Result |
|---|---|
| `ur.z-library.sk` | Browser: empty page (JS anti-bot); `web_extract`: summary only |
| `1lib.sk` | 503 Service Unavailable |
| `b-ok.org` | SSL cert mismatch |
| `z-lib.io` | SSL EOF |
| `z-lib.id` | 404 |
| `singlelogin.re` | Connection refused |

## Cloudflare-Protected (Browser Only)

| Domain | Notes |
|---|---|
| `oceanofpdf.com` | `web_extract` blocked. `browser_navigate` with stealth may pass. |
| `annas-archive.org` | SSL EOF from `execute_code`. Try `browser_navigate`. Low reliability. |
