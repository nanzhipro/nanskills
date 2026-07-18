# Commercial Book Investigation (Post-Search Phase)

When `ebook_fetch.py` returns `status: no_match` and the book is a recent commercial publication, extract purchase links and bibliographic details from retail and author sources.

## Amazon Product Page

Navigate to `https://www.amazon.com/dp/{ISBN10}` or search by title. Extract details via browser console:

```js
// Product details (publisher, date, pages, ISBN, dimensions, rank)
document.querySelector('#productDetails_detailBullets_sections1')?.innerText
|| document.querySelector('#detailBullets_feature_div')?.innerText

// Formats and prices are visible in the page snapshot
```

Key fields: ASIN, publisher, publication date, language, print length, ISBN-10/13, customer reviews (rating + count).

## Author Website / GitHub

For tech books especially, check:
- Author's personal site for free online editions or companion repos
- GitHub for `{book-slug}-book` repositories (e.g., `chiphuyen/aie-book`, `chiphuyen/dmls-book`)
- Companion repos often contain chapter summaries, code, and resources — note these as partial free alternatives even when the full book is not free

## Purchase Channels to Report

1. **Amazon Kindle** — instant delivery, usually cheapest digital option
2. **Amazon Paperback** — physical copy with shipping
3. **Publisher platform** — O'Reilly Learning, Manning LiveBook, etc. (subscription or one-time)
4. **Audiobook** — Audible/Amazon (mention if available with membership)

## Report Format

When no free copy exists, give the user:
- Confirmed bibliographic details (author, publisher, year, ISBN, pages)
- Per-source failure reasons (not just "not found")
- Purchase links with prices (use the currency shown on the page)
- Any free supplementary resources (companion repos, author blog posts, sample chapters)
