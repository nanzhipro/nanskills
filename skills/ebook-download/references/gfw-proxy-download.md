# GFW + System Proxy: Terminal Download Strategy

When behind GFW, the terminal cannot reach libgen.li directly (curl → 000,
cloudscraper may still work for search but the download CDN is unreachable or
extremely slow). However, many GFW users run a **system proxy** (Clash Verge,
V2Ray, etc.) that routes traffic through a local SOCKS/HTTP proxy.

## Detect the proxy

```bash
networksetup -getwebproxy Wi-Fi        # HTTP proxy
networksetup -getsecurewebproxy Wi-Fi  # HTTPS proxy
scutil --proxy | grep SOCKS            # SOCKS proxy
```

Typical Clash Verge proxy: `127.0.0.1:7897` (HTTP + SOCKS on same port).

## Download through the proxy

Set `HTTPS_PROXY` and `HTTP_PROXY` environment variables **before** importing
cloudscraper. The proxy routes the download traffic through the user's VPN,
bypassing GFW blocks on libgen's CDN.

```python
import os
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7897'
os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7897'

import cloudscraper
# ... download as usual
```

Do NOT use `curl --socks5` — the SOCKS5 path may not work for libgen's TLS
(SSL_ERROR_SYSCALL). Use the HTTP proxy via Python's `requests`/`cloudscraper`.

## Speed expectations

Through a GFW proxy, libgen large files download at **30-50 KB/s**. A 34 MB
file takes ~15-20 minutes. The foreground terminal timeout (600s) is NOT enough
for files >24 MB — use **background process + notify_on_complete**.

## Background download for large files

```bash
# 1. Get a fresh key from browser: browser_console → document.querySelector('a[href*="get.php"]').href
# 2. Start background download (no timeout limit):
terminal(background=true, notify_on_complete=true, command="""
/usr/bin/python3 << 'PYEOF'
import os, json, time, zipfile
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7897'
os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7897'
import cloudscraper

url = 'https://libgen.li/get.php?md5=MD5&key=FRESH_KEY'
path = os.path.expanduser('~/Downloads/Book.epub')

sc = cloudscraper.create_scraper()
start = time.time()
total = 0
try:
    r = sc.get(url, stream=True, timeout=(60, 3600))
    with open(path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=262144):
            if chunk:
                f.write(chunk)
                total += len(chunk)
    zf = zipfile.ZipFile(path)
    print(json.dumps({'ok':True,'size':total,'entries':len(zf.namelist())}))
    zf.close()
except Exception as e:
    print(json.dumps({'ok':False,'error':str(e)[:300],'downloaded':total}))
PYEOF
""")
# 3. Monitor: process(action='poll', session_id=...)
# 4. Also check file on disk: ls -lh ~/Downloads/Book.epub
```

## Anti-patterns

### Do NOT try Range resume
HTTP `Range: bytes=N-` header on libgen get.php consistently returns **HTTP 524**
(Cloudflare timeout). Each get.php key is session-bound — you can't resume a
download started with one key using another. Delete the partial file, get a
fresh key, and restart from scratch.

### Do NOT use Safari / computer_use for libgen downloads
`open -a Safari "https://libgen.li/get.php?...`" does not trigger a usable
download flow. The browser may show a blank page, hang, or download an HTML
error page. `computer_use` driving Safari to click GET links is equally
ineffective. Stick to terminal cloudscraper.

### Do NOT use foreground terminal for >24 MB files
The foreground `terminal()` timeout is 600s. At 30-40 KB/s proxy speeds, this
caps out at ~24 MB. Use background mode for anything larger.
