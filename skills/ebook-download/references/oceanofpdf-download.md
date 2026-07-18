# OceanofPDF Download Pattern

OceanofPDF is the primary source for new books (≤6 months old) not yet on libgen.
It is also the only major source that consistently has books published in 2026.

## Architecture

OceanofPDF is protected by **Cloudflare anti-bot**. The download does NOT use direct
links or redirects — it uses a **form POST** with server-side session validation.
This means curl/requests alone CANNOT download from OceanofPDF.

## Required Tool Stack

1. `computer_use` (or user's real Safari) — to pass Cloudflare challenge
2. `terminal` with `osascript` — to execute JavaScript in Safari and submit the form
3. The actual download happens in Safari, saving directly to `~/Downloads/`

## Step-by-Step

### Step 1: Enable Safari JavaScript from Apple Events

One-time setup — must be done before the first OceanofPDF download:

```bash
defaults write com.apple.Safari IncludeDevelopMenu -bool true
defaults write com.apple.Safari AllowJavaScriptFromAppleEvents -bool true
```

### Step 2: Navigate to OceanofPDF book page

```bash
open -a Safari "https://oceanofpdf.com/authors/<slug>/pdf-epub-<title-slug>-download/"
```

Wait 3-5 seconds for Cloudflare to resolve and page to load.

### Step 3: Find the download forms

OceanofPDF embeds two hidden POST forms in the page — one for PDF, one for EPUB:

```html
<form action="https://oceanofpdf.com/Fetching_Resource.php" method="post" target="_blank">
  <input name="id" type="hidden" value="srv3">
  <input name="filename" type="hidden" value="Book_Name.pdf">
</form>

<form action="https://oceanofpdf.com/Fetching_Resource.php" method="post" target="_blank">
  <input name="id" type="hidden" value="srv3">
  <input name="filename" type="hidden" value="Book_Name.epub">
</form>
```

### Step 4: Submit the EPUB form via AppleScript

```bash
osascript -e 'tell application "Safari" to return do JavaScript "
  document.querySelector(\"form[action*=\\\"Fetching_Resource\\\"] input[value$=\\\".epub\\\"]\")
    .closest(\"form\").submit();
  \"submitted\"
" in current tab of front window'
```

This opens a new Safari tab (`target="_blank"`) which triggers the actual file download.
The file saves to `~/Downloads/` with an `_OceanofPDF.com_` prefix.

### Step 5: Verify

```bash
ls -lh ~/Downloads/_OceanofPDF.com_*.epub   # >500KB expected
file ~/Downloads/_OceanofPDF.com_*.epub      # "EPUB document" or "Zip archive data"
python3 -c "
import zipfile
z = zipfile.ZipFile('~/Downloads/_OceanofPDF.com_*.epub')  # expand path
print(f'{len(z.namelist())} files')
"
```

## Pitfalls

- **`file` reports "Zip archive data" instead of "EPUB document"** — OceanofPDF doesn't
  guarantee the `mimetype` entry is first in the ZIP. The file is still valid and readable
  by most EPUB readers.
- **curl POST returns HTML not the file** — Fetching_Resource.php requires browser cookies
  and session state from the Cloudflare challenge. curl cannot replicate this.
- **Form submission opens in new tab** — the `target="_blank"` attribute means the file
  downloads in a new tab. Monitor `~/Downloads/` for the file, not the current page.
- **Cloudflare re-challenge** — if too much time passes between steps 2 and 4, Cloudflare may
  challenge again. Keep the flow under 2 minutes.

## Finding the Book on OceanofPDF

OceanofPDF doesn't have a search API. Find book URLs via:

```bash
web_search: site:oceanofpdf.com "<title>" "<author>"
```

The URL pattern is always:
```
https://oceanofpdf.com/authors/<author-slug>/pdf-epub-<title-slug>-download/
```
