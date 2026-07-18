# Case Study: 《我在日本熊野古道找回自己》

## Book Metadata (from Douban API)

**API**: `https://book.douban.com/j/subject_suggest?q=我在日本熊野古道找回自己`

```json
{
  "title": "我在日本熊野古道找回自己",
  "url": "https://book.douban.com/subject/38421789/",
  "pic": "https://img1.doubanio.com/view/subject/s/public/s35521030.jpg",
  "author_name": "克雷格.莫德",
  "year": "2026",
  "type": "b",
  "id": "38421789"
}
```

## Full Details (from Douban detail page)

| Field | Value |
|-------|-------|
| Chinese Title | 我在日本熊野古道找回自己 |
| Original Title | Things Become Other Things: A Walking Memoir |
| Author | 克雷格·莫德 (Craig Mod) |
| Translator | 尤可欣 |
| Publisher | 馬可孛羅文化 |
| Publish Date | 2026-06-04 |
| ISBN | 9786267747858 |
| Pages | 336 |
| Binding | 平装 |
| Price | NTD 480 |
| Original Publisher | Random House (2025) |

## LibGen Search Results

**Search URL**: `https://libgen.li/index.php?req=Things+Become+Other+Things+Craig+Mod&phrase=1&column=title&res=25`

**Results**:
- Edition ID: 150912955
- MD5: `c01520ac8826efaf5557441ee1406685`
- ISBNs: 9780593732540, 0593732545, 9780593732564, 0593732561
- LibGen ID: 6426481
- Also found: `Craig.Mod.-.Things.Become.Other.Things.A.Walking.Memoir.2025.RETAIL.EPUB.eBook-CTO`

## Download

**Download page**: `https://libgen.li/ads.php?md5=c01520ac8826efaf5557441ee1406685`

**GET link**: `get.php?md5=c01520ac8826efaf5557441ee1406685&key=TD4SIA4HAG3C4381`

**Final CDN URL**: `https://cdn5.booksdl.lc/get.php?md5=c01520ac8826efaf5557441ee1406685&key=TD4SIA4HAG3C4381`

**File**: EPUB, 6,937,416 bytes (6.6 MB), 183 internal entries (XHTML chapters)

## Key Takeaways

1. Douban's `subject_suggest` API is the fastest way to get book metadata — no JS rendering needed.
2. Chinese translations published within 2 weeks are almost never available as ebook scans yet. Fall back to the English original.
3. LibGen `.li` domain works when `.is` and `.rs` are SSL-blocked from Japan/Asia.
4. Cloudscraper is needed for LibGen.li (Cloudflare-protected).
5. The download key (`&key=...`) on `get.php` is session-tied — extract it fresh each time from `ads.php`.
