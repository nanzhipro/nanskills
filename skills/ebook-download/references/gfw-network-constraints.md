# GFW Network Constraints for Ebook Download

Last verified: 2026-07-14, from a Chinese mainland network (macOS 26.5.2).

## Terminal reachability (curl/cloudscraper)

| Site | Status | Detail |
|------|--------|--------|
| libgen.li | ❌ Timeout | curl exits 28, cloudscraper times out |
| libgen.is / .st / .gs | ❌ Timeout | All blocked |
| cdn4.booksdl.lc | ❌ Timeout | Download CDN blocked |
| annas-archive.org / .se | ❌ Connection closed | ERR_CONNECTION_CLOSED |
| annas-archive.li / .gl | ⚠️ JS challenge | HTTP 200 but empty page (Aliyun WAF) |
| oceanofpdf.com | ⚠️ Cloudflare | Cloudflare challenge blocks headless |
| vk.com | ⚠️ Slow/timeout | SPA loads but search is slow |
| Bing / Google | ✅ Works | Search engines pass through |

## Browser reachability (Browserbase, routes through Tokyo)

| Site | Status | Detail |
|------|--------|--------|
| libgen.li | ✅ Works | Search and ads.php pages load |
| libgen.vg | ✅ Works | Same as .li, different CF route |
| cdn4.booksdl.lc | ⚠️ 521/522 | CF reaches but origin is down |
| annas-archive.li / .gl | ❌ Empty page | JS-challenged, same as terminal |
| oceanofpdf.com | ❌ Cloudflare | Headless browser can't solve CF iframe |

## Effective strategy

1. **Search**: Use `browser_navigate` → libgen.li or libgen.vg
2. **Download**: 
   - Try libgen GET link → if 521/522, CDN is down (server-side outage, not network)
   - Fallback: OceanofPDF manual download (user's real Safari solves Cloudflare in seconds)
3. **Never**: run `libgen_fetch.py` behind GFW — guaranteed timeout (exit 124)

## CDN outage signature (521/522)

The download CDN `cdn4.booksdl.lc` returns Cloudflare error pages:
- 521: "Web server is down" — origin unreachable
- 522: "Connection timed out" — origin timeout

Both are server-side issues. No amount of key refreshing or retrying helps.
Resolution: wait (hours) or use OceanofPDF path.
