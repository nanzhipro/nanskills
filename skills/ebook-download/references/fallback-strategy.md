# Fallback Strategy

When libgen.li is unreachable (503) or the book is not found, try these sources in order. Each attempt costs time — bail after 2 failed attempts per source.

## Priority Order

### 0. libgen.li Retry
- If 503, retry up to 3 times with 0.5s间隔. If all 3 fail, immediately move to VK.com.
- libgen.li 503 is transient — don't wait, don't loop beyond 3.

### 1. VK.com — ✅ Most Reliable Fallback
- Search: `site:vk.com "{title}" {author} epub`
- Ebook-sharing communities like "Books & Magazines in English" (vk.com/onlythebestbooks) host direct `.epub` download links.
- URL pattern: `vk.com/doc{user_id}_{doc_id}?hash=...&api=1&no_preview=1`
- Download with: `requests.get(url, allow_redirects=True)` — NO key extraction needed, it's a direct link.
- **This is the #1 fallback.** Hit rate is very high for popular English non-fiction.

### 2. Z-Library — ⚠️ Long Shot
- Search: `site:z-library.sk "{title}" {author}`
- All 6 tested domains are dead or blocked.
- **Hard limit: 2 attempts, then move on.**

### 3. Anna's Archive — ⚠️ SSL Issues
- `https://annas-archive.org/search?q="{title}+{author}"`
- `execute_code` → SSL EOF. Try `browser_navigate` instead.

### 4. dokumen.pub -- reCAPTCHA Required
- Search: site:dokumen.pub "{title}"
- PDF-only in tested cases. Download flow requires Google reCAPTCHA -- cannot be automated.
- If this is the only available source, tell the user to open it manually in their browser.

### 5. Mobilism
- `https://forum.mobilism.org/search.php?keywords={title}`
- May require login. Low hit rate for new/non-fiction/self-published books.
- **Hard limit: 1 attempt.**

### 6. OceanofPDF
- Search: `site:oceanofpdf.com "{title}" {author}`
- Cloudflare-protected. Use `browser_navigate` with stealth features.

### 7. Broad Web Search
- Query: `"{title}" {author} epub OR pdf download`
- Scan results for VK links, unfamiliar mirrors, direct download links, or forum posts.

## When All Sources Fail

Report honestly: "在所有已知源中未找到此书。可能原因：书名过于新、自出版且未入库、或书名有误。建议检查书名拼写或提供 ISBN。"
