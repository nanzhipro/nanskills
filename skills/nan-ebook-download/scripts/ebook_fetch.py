#!/usr/bin/env python3
"""Search, download, and verify legally accessible ebooks.

The CLI emits one JSON document. It uses only Python's standard library and
never overwrites an existing file. Remote metadata is untrusted data.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import difflib
import hashlib
import json
import os
import re
import sys
import tempfile
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any, Iterable, Optional


VERSION = "6.0.0"
DEFAULT_MAX_BYTES = 200 * 1024 * 1024
MAX_METADATA_BYTES = 8 * 1024 * 1024
MAX_ZIP_ENTRIES = 20_000
MAX_ZIP_UNCOMPRESSED = 2 * 1024 * 1024 * 1024
MAX_ZIP_RATIO = 250
MAX_OPF_BYTES = 4 * 1024 * 1024
REMOTE_DATA_NOTICE = "untrusted_remote_data"


class FetchError(RuntimeError):
    status = "network_error"


class BlockedError(FetchError):
    status = "blocked"


class ParseError(FetchError):
    status = "parse_error"


class SizeLimitError(FetchError):
    status = "size_limit"


class NotConfiguredError(FetchError):
    status = "not_configured"


@dataclasses.dataclass
class Candidate:
    source: str
    title: str
    authors: list[str]
    fmt: str
    download_url: str
    allowed_hosts: tuple[str, ...]
    rights_basis: str
    rights_evidence: str
    landing_url: str
    languages: list[str] = dataclasses.field(default_factory=list)
    isbns: list[str] = dataclasses.field(default_factory=list)
    year: Optional[int] = None
    publisher: str = ""
    identifier: str = ""
    expected_size: int = 0
    expected_md5: str = ""
    access_country: str = ""
    matched_query: str = ""
    score: float = 0.0

    def public_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "title": clean_remote(self.title),
            "authors": [clean_remote(v) for v in self.authors[:8]],
            "format": self.fmt,
            "languages": self.languages[:8],
            "isbn": self.isbns[:8],
            "year": self.year,
            "publisher": clean_remote(self.publisher),
            "identifier": clean_remote(self.identifier),
            "landing_url": safe_report_url(self.landing_url),
            "rights_basis": clean_remote(self.rights_basis),
            "rights_evidence": safe_report_url(self.rights_evidence),
            "access_country": clean_remote(self.access_country),
            "expected_size": self.expected_size or None,
            "score": round(self.score, 2),
            "matched_query": clean_remote(self.matched_query),
            "remote_metadata_trust": REMOTE_DATA_NOTICE,
        }


@dataclasses.dataclass
class MetadataRecord:
    title: str
    authors: list[str]
    isbns: list[str]
    year: Optional[int]
    publisher: str
    languages: list[str]
    info_url: str
    source: str
    score: float = 0.0

    def public_dict(self) -> dict[str, Any]:
        return {
            "title": clean_remote(self.title),
            "authors": [clean_remote(v) for v in self.authors[:8]],
            "isbn": self.isbns[:8],
            "year": self.year,
            "publisher": clean_remote(self.publisher),
            "languages": self.languages[:8],
            "info_url": safe_report_url(self.info_url),
            "source": self.source,
            "score": round(self.score, 2),
            "remote_metadata_trust": REMOTE_DATA_NOTICE,
        }


@dataclasses.dataclass
class SourceOutcome:
    source: str
    status: str
    candidates: list[Candidate] = dataclasses.field(default_factory=list)
    error: str = ""
    detail: str = ""
    elapsed_ms: int = 0

    def public_dict(self) -> dict[str, Any]:
        data = {
            "source": self.source,
            "status": self.status,
            "candidate_count": len(self.candidates),
            "elapsed_ms": self.elapsed_ms,
        }
        if self.error:
            data["error"] = clean_remote(self.error, 240)
        if self.detail:
            data["detail"] = clean_remote(self.detail, 240)
        return data


def clean_remote(value: Any, limit: int = 300) -> str:
    """Constrain remote strings before emitting them to an agent."""
    text = str(value or "")
    text = "".join(ch if ch >= " " else " " for ch in text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def safe_report_url(url: str) -> str:
    """Report an HTTPS URL without credentials or sensitive query fields."""
    try:
        p = urllib.parse.urlsplit(url)
        port = p.port
    except ValueError:
        return ""
    if p.scheme != "https" or not p.hostname:
        return ""
    query = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
    redacted = []
    for key, value in query:
        if key.lower() in {"key", "token", "access_token", "signature", "auth"}:
            continue
        redacted.append((key, value))
    netloc = p.hostname
    if port and port != 443:
        netloc += f":{port}"
    return urllib.parse.urlunsplit(("https", netloc, p.path, urllib.parse.urlencode(redacted), ""))


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold()
    value = "".join(ch if ch.isalnum() or ch == "_" else " " for ch in value)
    return re.sub(r"\s+", " ", value).strip()


def text_tokens(value: str) -> set[str]:
    normalized = normalize_text(value)
    tokens = {t for t in normalized.split() if len(t) > 1}
    non_ascii = "".join(ch for ch in normalized if ord(ch) > 127 and ch.isalnum())
    if non_ascii:
        tokens.update(non_ascii[i : i + 2] for i in range(max(0, len(non_ascii) - 1)))
        if len(non_ascii) == 1:
            tokens.add(non_ascii)
    return tokens


def text_similarity(left: str, right: str) -> float:
    a, b = normalize_text(left), normalize_text(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    seq = difflib.SequenceMatcher(None, a, b).ratio()
    at, bt = text_tokens(a), text_tokens(b)
    overlap = len(at & bt) / max(1, len(at | bt))
    containment = 1.0 if a in b or b in a else 0.0
    # A title plus a subtitle should still match well, but a derivative work
    # containing the complete original title must not score as an exact match.
    return max(seq, overlap, containment * 0.88)


def author_similarity(expected: str, actual: Iterable[str]) -> float:
    expected_tokens = text_tokens(expected)
    if not expected_tokens:
        return 0.0
    best = 0.0
    for name in actual:
        tokens = text_tokens(name.replace(",", " "))
        if tokens:
            best = max(best, len(tokens & expected_tokens) / max(1, min(len(tokens), len(expected_tokens))))
    return best


def normalize_isbn(value: str) -> str:
    return re.sub(r"[^0-9Xx]", "", value or "").upper()


def valid_isbn(value: str) -> bool:
    isbn = normalize_isbn(value)
    if len(isbn) == 10:
        total = 0
        for i, ch in enumerate(isbn):
            digit = 10 if ch == "X" and i == 9 else int(ch) if ch.isdigit() else -1
            if digit < 0:
                return False
            total += (10 - i) * digit
        return total % 11 == 0
    if len(isbn) == 13 and isbn.isdigit():
        total = sum(int(ch) * (1 if i % 2 == 0 else 3) for i, ch in enumerate(isbn[:12]))
        return (10 - total % 10) % 10 == int(isbn[-1])
    return False


def parse_year(value: Any) -> Optional[int]:
    match = re.search(r"\b(1[0-9]{3}|20[0-9]{2}|2100)\b", str(value or ""))
    return int(match.group(1)) if match else None


def truthy(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"true", "1", "yes"}


def read_key_file(value: str) -> str:
    path = Path(value).expanduser()
    stat = path.lstat()
    if path.is_symlink() or not path.is_file() or stat.st_size > 4096:
        raise ValueError("key file must be a small regular file, not a symlink")
    if stat.st_mode & 0o077:
        raise ValueError("key file must not be group/world accessible")
    key = path.read_text(encoding="utf-8").strip()
    if not key or len(key) > 512:
        raise ValueError("key file is empty or malformed")
    return key


def host_allowed(host: str, allowed_hosts: Iterable[str]) -> bool:
    host = (host or "").lower().rstrip(".")
    return any(host == suffix or host.endswith("." + suffix) for suffix in allowed_hosts)


def validate_https_url(url: str, allowed_hosts: Iterable[str]) -> None:
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise BlockedError(f"invalid URL: {exc}") from exc
    if parsed.scheme != "https" or not parsed.hostname:
        raise BlockedError("only HTTPS URLs are allowed")
    if parsed.username or parsed.password or (port not in (None, 443)):
        raise BlockedError("credentials and non-HTTPS ports are not allowed")
    if not host_allowed(parsed.hostname, allowed_hosts):
        raise BlockedError(f"redirect/download host is not allowlisted: {parsed.hostname}")


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_hosts: tuple[str, ...]):
        super().__init__()
        self.allowed_hosts = allowed_hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        validate_https_url(newurl, self.allowed_hosts)
        if len(getattr(req, "redirect_dict", {}) or {}) >= 5:
            raise BlockedError("too many redirects")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class HttpClient:
    """HTTPS client with bounded reads, safe redirects, and light rate limiting."""

    def __init__(self, timeout: float, contact_email: str = ""):
        self.timeout = timeout
        self.contact_email = clean_remote(contact_email, 120)
        self._lock = threading.Lock()
        self._last_request: dict[str, float] = {}

    @property
    def user_agent(self) -> str:
        suffix = f" (contact: {self.contact_email})" if self.contact_email else ""
        return f"ebook-search-and-download/{VERSION}{suffix}"

    def _rate_limit(self, host: str) -> None:
        interval = 0.0
        if host == "openlibrary.org":
            interval = 0.34 if self.contact_email else 1.05
        elif host in {"gutendex.com", "library.oapen.org", "archive.org"}:
            interval = 0.35
        if not interval:
            return
        with self._lock:
            now = time.monotonic()
            wait = interval - (now - self._last_request.get(host, 0.0))
            if wait > 0:
                time.sleep(wait)
            self._last_request[host] = time.monotonic()

    def open(self, url: str, allowed_hosts: tuple[str, ...], accept: str):
        validate_https_url(url, allowed_hosts)
        host = urllib.parse.urlsplit(url).hostname or ""
        self._rate_limit(host)
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": accept,
                "Accept-Encoding": "identity",
            },
        )
        opener = urllib.request.build_opener(_SafeRedirectHandler(allowed_hosts))
        try:
            return opener.open(request, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403, 407, 429, 451}:
                raise BlockedError(f"HTTP {exc.code}") from exc
            raise FetchError(f"HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise FetchError(type(exc).__name__) from exc

    def get_bytes(
        self,
        url: str,
        allowed_hosts: tuple[str, ...],
        *,
        accept: str,
        max_bytes: int,
    ) -> tuple[bytes, str]:
        with self.open(url, allowed_hosts, accept) as response:
            content_type = response.headers.get_content_type().lower()
            length = response.headers.get("Content-Length")
            if length and length.isdigit() and int(length) > max_bytes:
                raise SizeLimitError(f"response exceeds {max_bytes} bytes")
            chunks: list[bytes] = []
            size = 0
            while True:
                chunk = response.read(min(64 * 1024, max_bytes + 1 - size))
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise SizeLimitError(f"response exceeds {max_bytes} bytes")
                chunks.append(chunk)
            return b"".join(chunks), content_type

    def get_json(self, url: str, allowed_hosts: tuple[str, ...]) -> Any:
        raw, content_type = self.get_bytes(
            url,
            allowed_hosts,
            accept="application/json",
            max_bytes=MAX_METADATA_BYTES,
        )
        if "json" not in content_type and not raw.lstrip().startswith((b"{", b"[")):
            raise ParseError(f"expected JSON, got {content_type}")
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ParseError("invalid JSON response") from exc


def timed_source(name: str, fn) -> SourceOutcome:  # noqa: ANN001
    started = time.monotonic()
    try:
        candidates, detail = fn()
        status = "ok" if candidates else "no_match"
        outcome = SourceOutcome(name, status, candidates=candidates, detail=detail)
    except FetchError as exc:
        outcome = SourceOutcome(name, exc.status, error=str(exc))
    except (KeyError, TypeError, ValueError) as exc:
        outcome = SourceOutcome(name, "parse_error", error=type(exc).__name__)
    outcome.elapsed_ms = int((time.monotonic() - started) * 1000)
    return outcome


def gutendex_candidates(data: Any, query: str) -> list[Candidate]:
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise ParseError("Gutendex schema changed")
    out: list[Candidate] = []
    for item in data["results"][:32]:
        if not isinstance(item, dict):
            continue
        if item.get("media_type") != "Text" or item.get("copyright") is not False:
            continue
        formats = item.get("formats") if isinstance(item.get("formats"), dict) else {}
        epub = formats.get("application/epub+zip")
        if not isinstance(epub, str) or not epub.startswith("https://"):
            continue
        try:
            validate_https_url(epub, ("gutenberg.org",))
        except BlockedError:
            continue
        authors = []
        for author in item.get("authors", [])[:8]:
            if isinstance(author, dict) and author.get("name"):
                authors.append(clean_remote(author["name"]))
        identifier = str(item.get("id") or "")
        out.append(
            Candidate(
                source="gutenberg",
                title=clean_remote(item.get("title")),
                authors=authors,
                fmt="epub",
                download_url=epub,
                allowed_hosts=("gutenberg.org",),
                rights_basis="Project Gutenberg catalog: copyright=false (US public domain)",
                rights_evidence=f"https://www.gutenberg.org/ebooks/{identifier}",
                landing_url=f"https://www.gutenberg.org/ebooks/{identifier}",
                languages=[clean_remote(v, 20) for v in item.get("languages", [])[:8]],
                identifier=identifier,
                matched_query=query,
            )
        )
    return out


def search_gutenberg(client: HttpClient, query: str, author: str) -> tuple[list[Candidate], str]:
    search = " ".join(part for part in (query, author) if part).strip()
    params = urllib.parse.urlencode(
        {
            "search": search,
            "copyright": "false",
            "mime_type": "application/epub+zip",
        }
    )
    data = client.get_json(f"https://gutendex.com/books/?{params}", ("gutendex.com",))
    return gutendex_candidates(data, query), "US public-domain catalog"


def metadata_map(item: dict[str, Any]) -> dict[str, list[str]]:
    raw = item.get("metadata")
    out: dict[str, list[str]] = {}
    if isinstance(raw, list):
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            key, value = entry.get("key"), entry.get("value")
            if key and value is not None:
                out.setdefault(str(key), []).append(clean_remote(value))
    elif isinstance(raw, dict):
        for key, values in raw.items():
            if isinstance(values, list):
                for value in values:
                    if isinstance(value, dict):
                        value = value.get("value")
                    if value is not None:
                        out.setdefault(str(key), []).append(clean_remote(value))
            elif values is not None:
                out.setdefault(str(key), []).append(clean_remote(values))
    return out


def first_meta(meta: dict[str, list[str]], *keys: str) -> str:
    for key in keys:
        if meta.get(key):
            return meta[key][0]
    return ""


def all_meta(meta: dict[str, list[str]], *keys: str) -> list[str]:
    values: list[str] = []
    for key in keys:
        values.extend(meta.get(key, []))
    return list(dict.fromkeys(v for v in values if v))


def recognized_open_license(values: Iterable[str]) -> str:
    for value in values:
        lower = value.casefold()
        if any(
            token in lower
            for token in (
                "creativecommons.org/licenses/",
                "creativecommons.org/publicdomain/",
                "cc by",
                "cc-by",
                "cc_by",
                "cc0",
                "creative commons",
                "public domain",
                "open access",
            )
        ):
            return clean_remote(value)
    return ""


def oapen_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [v for v in data if isinstance(v, dict)]
    if not isinstance(data, dict):
        raise ParseError("OAPEN schema changed")
    for key in ("items", "results", "objects"):
        if isinstance(data.get(key), list):
            return [v for v in data[key] if isinstance(v, dict)]
    embedded = data.get("_embedded")
    if isinstance(embedded, dict):
        for value in embedded.values():
            if isinstance(value, list):
                return [v for v in value if isinstance(v, dict)]
    return []


def oapen_bitstreams(item: dict[str, Any]) -> list[dict[str, Any]]:
    raw = item.get("bitstreams")
    if isinstance(raw, list):
        return [v for v in raw if isinstance(v, dict)]
    embedded = item.get("_embedded")
    if isinstance(embedded, dict):
        raw = embedded.get("bitstreams")
        if isinstance(raw, list):
            return [v for v in raw if isinstance(v, dict)]
    return []


def parse_oapen(data: Any, query: str) -> tuple[list[Candidate], int]:
    out: list[Candidate] = []
    records = oapen_items(data)
    for item in records[:30]:
        meta = metadata_map(item)
        title = first_meta(meta, "dc.title", "dc.title.alternative") or clean_remote(item.get("name"))
        authors = all_meta(meta, "dc.contributor.author", "dc.creator")
        isbns = [normalize_isbn(v) for v in all_meta(meta, "dc.identifier.isbn") if valid_isbn(v)]
        publisher = first_meta(meta, "dc.publisher")
        year = parse_year(first_meta(meta, "dc.date.issued", "dc.date"))
        languages = all_meta(meta, "dc.language.iso", "dc.language")
        license_values = all_meta(meta, "dc.rights", "dc.rights.uri", "dc.license")
        license_text = recognized_open_license(license_values)
        if not title or not license_text:
            continue
        handle = clean_remote(item.get("handle"), 160)
        uuid = clean_remote(item.get("uuid") or item.get("id"), 100)
        landing = (
            f"https://library.oapen.org/handle/{urllib.parse.quote(handle, safe='/')}"
            if handle
            else f"https://library.oapen.org/items/{urllib.parse.quote(uuid)}"
        )
        for bitstream in oapen_bitstreams(item):
            name = clean_remote(bitstream.get("name"), 220)
            mime = clean_remote(bitstream.get("mimeType") or bitstream.get("format"), 100).lower()
            fmt = "epub" if name.lower().endswith(".epub") or mime == "application/epub+zip" else ""
            if not fmt and (name.lower().endswith(".pdf") or mime == "application/pdf"):
                fmt = "pdf"
            if not fmt:
                continue
            link = bitstream.get("retrieveLink") or bitstream.get("downloadUrl") or bitstream.get("url")
            if not isinstance(link, str):
                links = bitstream.get("_links")
                if isinstance(links, dict):
                    content = links.get("content") or links.get("self")
                    if isinstance(content, dict):
                        link = content.get("href")
            if not isinstance(link, str) or not link:
                continue
            download_url = urllib.parse.urljoin("https://library.oapen.org/", link)
            try:
                validate_https_url(download_url, ("library.oapen.org",))
            except BlockedError:
                continue
            checksum = bitstream.get("checkSum") or bitstream.get("checksum")
            expected_md5 = ""
            if isinstance(checksum, dict) and str(checksum.get("checkSumAlgorithm", "")).upper() == "MD5":
                expected_md5 = str(checksum.get("value") or "").lower()
            elif isinstance(checksum, str) and re.fullmatch(r"[a-fA-F0-9]{32}", checksum):
                expected_md5 = checksum.lower()
            size = bitstream.get("sizeBytes") or bitstream.get("size") or 0
            try:
                expected_size = int(size)
            except (TypeError, ValueError):
                expected_size = 0
            out.append(
                Candidate(
                    source="oapen",
                    title=title,
                    authors=authors,
                    fmt=fmt,
                    download_url=download_url,
                    allowed_hosts=("library.oapen.org",),
                    rights_basis=f"OAPEN open-access record: {license_text}",
                    rights_evidence=landing,
                    landing_url=landing,
                    languages=languages,
                    isbns=isbns,
                    year=year,
                    publisher=publisher,
                    identifier=handle or uuid,
                    expected_size=expected_size,
                    expected_md5=expected_md5,
                    matched_query=query,
                )
            )
    return out, len(records)


def search_oapen(client: HttpClient, query: str, author: str, isbn: str) -> tuple[list[Candidate], str]:
    term = (isbn or query).replace('"', " ").strip()
    field = "dc.identifier.isbn" if isbn else "dc.title"
    expression = f'{field}:"{term}"'
    if author and not isbn:
        expression += f' AND dc.contributor.author:"{author.replace(chr(34), " ")}"'
    params = urllib.parse.urlencode({"query": expression, "expand": "metadata,bitstreams", "limit": 30})
    data = client.get_json(f"https://library.oapen.org/rest/search?{params}", ("library.oapen.org",))
    candidates, records = parse_oapen(data, query)
    return candidates, f"{records} OA record(s) inspected"


def choose_archive_files(files: Any, include_pdf: bool) -> list[dict[str, Any]]:
    if not isinstance(files, list):
        return []
    grouped: dict[str, list[dict[str, Any]]] = {"epub": [], "pdf": []}
    for item in files:
        if not isinstance(item, dict) or truthy(item.get("private")):
            continue
        name = str(item.get("name") or "")
        lower = name.lower()
        if any(token in lower for token in ("encrypted", ".acsm", "printdisabled")):
            continue
        fmt = "epub" if lower.endswith(".epub") else "pdf" if include_pdf and lower.endswith(".pdf") else ""
        if fmt:
            grouped[fmt].append(item)

    def key(item: dict[str, Any]) -> tuple[int, int, int]:
        source = 0 if str(item.get("source", "")).lower() == "original" else 1
        name = str(item.get("name") or "").lower()
        generated_penalty = 1 if any(v in name for v in ("_text", "_bw", "_noimages")) else 0
        try:
            size = int(item.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        return source, generated_penalty, -size

    selected = []
    if grouped["epub"]:
        selected.append(sorted(grouped["epub"], key=key)[0])
    if include_pdf and grouped["pdf"]:
        selected.append(sorted(grouped["pdf"], key=key)[0])
    return selected


def openlibrary_candidates(
    client: HttpClient,
    data: Any,
    query: str,
    include_pdf: bool,
) -> tuple[list[Candidate], int]:
    if not isinstance(data, dict) or not isinstance(data.get("docs"), list):
        raise ParseError("Open Library schema changed")
    out: list[Candidate] = []
    item_checks = 0
    for doc in data["docs"][:10]:
        if not isinstance(doc, dict):
            continue
        if doc.get("ebook_access") != "public" or doc.get("public_scan_b") is not True:
            continue
        ia_values = doc.get("ia") if isinstance(doc.get("ia"), list) else []
        for identifier in ia_values[:2]:
            if item_checks >= 5:
                break
            identifier = clean_remote(identifier, 120)
            if not re.fullmatch(r"[A-Za-z0-9._-]+", identifier):
                continue
            item_checks += 1
            metadata_url = f"https://archive.org/metadata/{urllib.parse.quote(identifier)}"
            item = client.get_json(metadata_url, ("archive.org",))
            metadata = item.get("metadata") if isinstance(item, dict) else None
            if not isinstance(metadata, dict) or truthy(metadata.get("access-restricted-item")):
                continue
            collections = metadata.get("collection")
            if isinstance(collections, str):
                collections = [collections]
            if isinstance(collections, list) and any("printdisabled" in str(v).lower() for v in collections):
                continue
            for file_info in choose_archive_files(item.get("files"), include_pdf):
                name = str(file_info.get("name") or "")
                fmt = "epub" if name.lower().endswith(".epub") else "pdf"
                quoted_name = urllib.parse.quote(name, safe="")
                download_url = f"https://archive.org/download/{identifier}/{quoted_name}"
                size = file_info.get("size") or 0
                try:
                    expected_size = int(size)
                except (TypeError, ValueError):
                    expected_size = 0
                md5 = str(file_info.get("md5") or "").lower()
                if not re.fullmatch(r"[a-f0-9]{32}", md5):
                    md5 = ""
                key = clean_remote(doc.get("key"), 120)
                landing = f"https://openlibrary.org{key}" if key.startswith("/") else f"https://archive.org/details/{identifier}"
                isbns = [normalize_isbn(v) for v in doc.get("isbn", [])[:20] if valid_isbn(v)]
                out.append(
                    Candidate(
                        source="openlibrary",
                        title=clean_remote(doc.get("title")),
                        authors=[clean_remote(v) for v in doc.get("author_name", [])[:8]],
                        fmt=fmt,
                        download_url=download_url,
                        allowed_hosts=("archive.org",),
                        rights_basis="Open Library public scan; Internet Archive item and file unrestricted",
                        rights_evidence=landing,
                        landing_url=landing,
                        languages=[clean_remote(v, 20) for v in doc.get("language", [])[:8]],
                        isbns=isbns,
                        year=parse_year(doc.get("first_publish_year")),
                        publisher=clean_remote((doc.get("publisher") or [""])[0] if isinstance(doc.get("publisher"), list) else doc.get("publisher")),
                        identifier=identifier,
                        expected_size=expected_size,
                        expected_md5=md5,
                        matched_query=query,
                    )
                )
    return out, item_checks


def search_openlibrary(
    client: HttpClient,
    query: str,
    author: str,
    isbn: str,
    include_pdf: bool,
) -> tuple[list[Candidate], str]:
    params: dict[str, Any] = {
        "limit": 10,
        "ebook_access": "public",
        "fields": "key,title,author_name,isbn,language,first_publish_year,publisher,ia,ebook_access,public_scan_b",
    }
    if isbn:
        params["q"] = f"isbn:{isbn}"
    else:
        params["q"] = " ".join(value for value in (query, author) if value)
    data = client.get_json(
        "https://openlibrary.org/search.json?" + urllib.parse.urlencode(params),
        ("openlibrary.org",),
    )
    candidates, checks = openlibrary_candidates(client, data, query, include_pdf)
    return candidates, f"{checks} public Internet Archive item(s) inspected"


def googlebooks_candidates(data: Any, query: str, include_pdf: bool) -> list[Candidate]:
    if not isinstance(data, dict):
        raise ParseError("Google Books schema changed")
    items = data.get("items", [])
    if not isinstance(items, list):
        return []
    out: list[Candidate] = []
    for item in items[:40]:
        if not isinstance(item, dict):
            continue
        volume = item.get("volumeInfo") if isinstance(item.get("volumeInfo"), dict) else {}
        access = item.get("accessInfo") if isinstance(item.get("accessInfo"), dict) else {}
        if access.get("accessViewStatus") != "FULL_PUBLIC_DOMAIN" or access.get("publicDomain") is not True:
            continue
        download_access = access.get("downloadAccess")
        if isinstance(download_access, dict) and download_access.get("restricted") is True:
            continue
        identifiers = []
        for value in volume.get("industryIdentifiers", [])[:10]:
            if isinstance(value, dict) and valid_isbn(value.get("identifier", "")):
                identifiers.append(normalize_isbn(value["identifier"]))
        formats = [("epub", access.get("epub"))]
        if include_pdf:
            formats.append(("pdf", access.get("pdf")))
        for fmt, info in formats:
            if not isinstance(info, dict) or info.get("isAvailable") is not True:
                continue
            link = info.get("downloadLink")
            if not isinstance(link, str) or not link:
                continue
            parsed = urllib.parse.urlsplit(link)
            if parsed.scheme == "http" and host_allowed(parsed.hostname or "", ("books.google.com", "googleusercontent.com")):
                link = urllib.parse.urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, ""))
            try:
                validate_https_url(link, ("books.google.com", "googleusercontent.com"))
            except BlockedError:
                continue
            landing = volume.get("infoLink") or volume.get("canonicalVolumeLink") or "https://books.google.com/"
            out.append(
                Candidate(
                    source="googlebooks",
                    title=clean_remote(volume.get("title")),
                    authors=[clean_remote(v) for v in volume.get("authors", [])[:8]],
                    fmt=fmt,
                    download_url=link,
                    allowed_hosts=("books.google.com", "googleusercontent.com"),
                    rights_basis=f"Google Books FULL_PUBLIC_DOMAIN in {clean_remote(access.get('country'), 12) or 'reported country'}",
                    rights_evidence=str(landing),
                    landing_url=str(landing),
                    languages=[clean_remote(volume.get("language"), 20)] if volume.get("language") else [],
                    isbns=identifiers,
                    year=parse_year(volume.get("publishedDate")),
                    publisher=clean_remote(volume.get("publisher")),
                    identifier=clean_remote(item.get("id"), 100),
                    access_country=clean_remote(access.get("country"), 12),
                    matched_query=query,
                )
            )
    return out


def search_googlebooks(
    client: HttpClient,
    api_key: str,
    query: str,
    author: str,
    isbn: str,
    include_pdf: bool,
) -> tuple[list[Candidate], str]:
    if not api_key:
        raise NotConfiguredError("Google Books API key file is not configured")
    q = f"isbn:{isbn}" if isbn else " ".join(value for value in (query, author) if value)
    request_params = {
        "q": q,
        "filter": "free-ebooks",
        "printType": "books",
        "maxResults": 40,
        "key": api_key,
    }
    if not include_pdf:
        request_params["download"] = "epub"
    params = urllib.parse.urlencode(request_params)
    data = client.get_json(
        f"https://www.googleapis.com/books/v1/volumes?{params}",
        ("googleapis.com",),
    )
    return googlebooks_candidates(data, query, include_pdf), "public-domain filter applied"


def metadata_from_openlibrary(client: HttpClient, query: str, author: str, isbn: str) -> list[MetadataRecord]:
    params: dict[str, Any] = {
        "limit": 8,
        "fields": "key,title,author_name,isbn,language,first_publish_year,publisher",
    }
    if isbn:
        params["q"] = f"isbn:{isbn}"
    else:
        params["q"] = " ".join(value for value in (query, author) if value)
    data = client.get_json(
        "https://openlibrary.org/search.json?" + urllib.parse.urlencode(params),
        ("openlibrary.org",),
    )
    if not isinstance(data, dict) or not isinstance(data.get("docs"), list):
        raise ParseError("Open Library metadata schema changed")
    out = []
    for doc in data["docs"][:8]:
        if not isinstance(doc, dict) or not doc.get("title"):
            continue
        key = clean_remote(doc.get("key"), 120)
        out.append(
            MetadataRecord(
                title=clean_remote(doc.get("title")),
                authors=[clean_remote(v) for v in doc.get("author_name", [])[:8]],
                isbns=[normalize_isbn(v) for v in doc.get("isbn", [])[:20] if valid_isbn(v)],
                year=parse_year(doc.get("first_publish_year")),
                publisher=clean_remote((doc.get("publisher") or [""])[0] if isinstance(doc.get("publisher"), list) else doc.get("publisher")),
                languages=[clean_remote(v, 20) for v in doc.get("language", [])[:8]],
                info_url=f"https://openlibrary.org{key}" if key.startswith("/") else "https://openlibrary.org/",
                source="openlibrary",
            )
        )
    return out


def metadata_from_google(client: HttpClient, api_key: str, query: str, author: str, isbn: str) -> list[MetadataRecord]:
    if not api_key:
        return []
    q = f"isbn:{isbn}" if isbn else " ".join(value for value in (query, author) if value)
    params = urllib.parse.urlencode({"q": q, "printType": "books", "maxResults": 10, "key": api_key})
    data = client.get_json(
        f"https://www.googleapis.com/books/v1/volumes?{params}",
        ("googleapis.com",),
    )
    if not isinstance(data, dict):
        raise ParseError("Google Books metadata schema changed")
    out = []
    for item in data.get("items", [])[:10]:
        if not isinstance(item, dict):
            continue
        volume = item.get("volumeInfo") if isinstance(item.get("volumeInfo"), dict) else {}
        if not volume.get("title"):
            continue
        isbns = []
        for ident in volume.get("industryIdentifiers", [])[:10]:
            if isinstance(ident, dict) and valid_isbn(ident.get("identifier", "")):
                isbns.append(normalize_isbn(ident["identifier"]))
        out.append(
            MetadataRecord(
                title=clean_remote(volume.get("title")),
                authors=[clean_remote(v) for v in volume.get("authors", [])[:8]],
                isbns=isbns,
                year=parse_year(volume.get("publishedDate")),
                publisher=clean_remote(volume.get("publisher")),
                languages=[clean_remote(volume.get("language"), 20)] if volume.get("language") else [],
                info_url=str(volume.get("infoLink") or volume.get("canonicalVolumeLink") or "https://books.google.com/"),
                source="googlebooks",
            )
        )
    return out


def score_metadata(record: MetadataRecord, query: str, author: str, isbn: str) -> float:
    score = text_similarity(query, record.title) * 70 if query else 0.0
    if author:
        score += author_similarity(author, record.authors) * 30
    if isbn and normalize_isbn(isbn) in record.isbns:
        score += 150
    return score


def resolve_metadata(
    client: HttpClient,
    api_key: str,
    query: str,
    author: str,
    isbn: str,
) -> tuple[list[MetadataRecord], list[dict[str, Any]]]:
    jobs = {"openlibrary": lambda: metadata_from_openlibrary(client, query, author, isbn)}
    records: list[MetadataRecord] = []
    attempts: list[dict[str, Any]] = []
    if api_key:
        jobs["googlebooks"] = lambda: metadata_from_google(client, api_key, query, author, isbn)
    else:
        attempts.append({"source": "googlebooks", "status": "not_configured", "count": 0})
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        future_map = {pool.submit(fn): name for name, fn in jobs.items()}
        for future in concurrent.futures.as_completed(future_map):
            name = future_map[future]
            try:
                result = future.result()
                records.extend(result)
                attempts.append({"source": name, "status": "ok" if result else "no_match", "count": len(result)})
            except FetchError as exc:
                attempts.append({"source": name, "status": exc.status, "error": clean_remote(str(exc), 160)})
            except (KeyError, TypeError, ValueError):
                attempts.append({"source": name, "status": "parse_error"})
    dedup: dict[tuple[str, str], MetadataRecord] = {}
    for record in records:
        record.score = score_metadata(record, query, author, isbn)
        key = (normalize_text(record.title), normalize_text(record.authors[0] if record.authors else ""))
        if key not in dedup or record.score > dedup[key].score:
            dedup[key] = record
    ranked = sorted(dedup.values(), key=lambda r: -r.score)
    return ranked[:10], sorted(attempts, key=lambda v: v["source"])


def score_candidate(
    candidate: Candidate,
    queries: list[str],
    author: str,
    isbn: str,
    year: Optional[int],
    publisher: str,
    language: str,
) -> Optional[float]:
    if isbn and normalize_isbn(isbn) not in candidate.isbns:
        return None
    if year is not None and candidate.year != year:
        return None
    if publisher:
        if not candidate.publisher or text_similarity(publisher, candidate.publisher) < 0.75:
            return None
    if language:
        wanted = language.casefold()
        if not candidate.languages or not any(v.casefold().startswith(wanted) for v in candidate.languages):
            return None
    title_score = max((text_similarity(q, candidate.title) for q in queries if q), default=0.0)
    if not isbn and title_score < 0.5:
        return None
    author_score = author_similarity(author, candidate.authors) if author else 0.0
    if author and (not candidate.authors or author_score < 0.5):
        return None
    score = title_score * 100 + author_score * 35
    if isbn:
        score += 180
    score += 80 if candidate.fmt == "epub" else 0
    score += {"oapen": 24, "gutenberg": 20, "openlibrary": 12, "googlebooks": 10}.get(candidate.source, 0)
    return score


def local_name(path: Path) -> str:
    return normalize_text(re.sub(r"[_-]+", " ", path.stem))


def read_epub_metadata(path: Path) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if not infos or len(infos) > MAX_ZIP_ENTRIES:
            raise ValueError("invalid EPUB entry count")
        total_uncompressed = sum(info.file_size for info in infos)
        total_compressed = max(1, sum(max(0, info.compress_size) for info in infos))
        if total_uncompressed > MAX_ZIP_UNCOMPRESSED or total_uncompressed / total_compressed > MAX_ZIP_RATIO:
            raise ValueError("suspicious EPUB compression ratio")
        names = {info.filename for info in infos}
        if "mimetype" not in names or "META-INF/container.xml" not in names:
            raise ValueError("missing EPUB mimetype or container.xml")
        mimetype = archive.read("mimetype")
        if mimetype.strip() != b"application/epub+zip":
            raise ValueError("invalid EPUB mimetype")
        container_info = archive.getinfo("META-INF/container.xml")
        if container_info.file_size > 512 * 1024:
            raise ValueError("container.xml is too large")
        try:
            container = ET.fromstring(archive.read(container_info))
        except ET.ParseError as exc:
            raise ValueError("invalid container.xml") from exc
        rootfile = next((e for e in container.iter() if e.tag.rsplit("}", 1)[-1] == "rootfile"), None)
        opf_path = rootfile.get("full-path") if rootfile is not None else ""
        if not opf_path or opf_path not in names:
            raise ValueError("OPF path is missing")
        opf_info = archive.getinfo(opf_path)
        if opf_info.file_size > MAX_OPF_BYTES:
            raise ValueError("OPF is too large")
        try:
            opf_raw = archive.read(opf_info)
            opf = ET.fromstring(opf_raw)
        except ET.ParseError as exc:
            raise ValueError("invalid OPF") from exc
        drm_markers = (
            "adobe.com/adept",
            "acs-token",
            "encryptedkey",
            "readium.org/2014/01/lcp",
        )
        probe_names = [
            n
            for n in ("META-INF/rights.xml", "META-INF/encryption.xml", "META-INF/license.lcpl")
            if n in names
        ]
        for name in probe_names:
            info = archive.getinfo(name)
            if info.file_size <= 2 * 1024 * 1024:
                lower = archive.read(info).decode("utf-8", "ignore").casefold()
                if any(marker in lower for marker in drm_markers):
                    raise ValueError("DRM/encrypted EPUB is not accepted")
        bad = archive.testzip()
        if bad:
            raise ValueError("EPUB CRC check failed")

    titles, creators, identifiers = [], [], []
    for element in opf.iter():
        name = element.tag.rsplit("}", 1)[-1].casefold()
        text = clean_remote(element.text, 300)
        if not text:
            continue
        if name == "title":
            titles.append(text)
        elif name == "creator":
            creators.append(text)
        elif name == "identifier":
            identifiers.append(text)
    if not titles:
        warnings.append("OPF has no title")
    return {
        "title": titles[:8],
        "creator": creators[:8],
        "identifier": identifiers[:12],
        "entries": len(infos),
        "uncompressed_bytes": total_uncompressed,
    }, warnings


def identity_from_epub(
    metadata: dict[str, Any],
    expected_title: str,
    expected_authors: list[str],
    expected_isbns: list[str],
) -> tuple[str, list[str]]:
    warnings: list[str] = []
    titles = metadata.get("title", [])
    creators = metadata.get("creator", [])
    identifiers = metadata.get("identifier", [])
    if not expected_title:
        return "structure_only", ["no expected title was supplied"]
    title_score = max((text_similarity(expected_title, title) for title in titles), default=0.0)
    if title_score < 0.5:
        return "mismatch", ["OPF title does not match the selected candidate"]
    if expected_authors and creators:
        expected_author = " ".join(expected_authors)
        if author_similarity(expected_author, creators) < 0.45:
            return "mismatch", ["OPF creator does not match the selected candidate"]
    elif expected_authors and not creators:
        warnings.append("OPF has no creator; title and source metadata used")
    wanted_isbns = {normalize_isbn(v) for v in expected_isbns if valid_isbn(v)}
    found_isbns = {normalize_isbn(v) for v in identifiers if valid_isbn(v)}
    if wanted_isbns and found_isbns and not (wanted_isbns & found_isbns):
        return "mismatch", ["OPF ISBN conflicts with the selected edition"]
    if wanted_isbns and not found_isbns:
        warnings.append("OPF contains no parseable ISBN")
    return "matched", warnings


def verify_ebook(
    path: Path,
    fmt: str,
    *,
    expected_title: str = "",
    expected_authors: Optional[list[str]] = None,
    expected_isbns: Optional[list[str]] = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> tuple[bool, dict[str, Any], str]:
    expected_authors = expected_authors or []
    expected_isbns = expected_isbns or []
    try:
        stat = path.stat()
        if not path.is_file() or path.is_symlink() or stat.st_size < 1024:
            return False, {}, "file is missing, symlinked, or too small"
        if stat.st_size > max_bytes:
            return False, {}, f"file exceeds {max_bytes} bytes"
        sha256 = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                sha256.update(chunk)
        info: dict[str, Any] = {"bytes": stat.st_size, "sha256": sha256.hexdigest(), "format": fmt}
        if fmt == "epub":
            if not zipfile.is_zipfile(path):
                return False, info, "not a ZIP/EPUB file"
            metadata, warnings = read_epub_metadata(path)
            identity, identity_warnings = identity_from_epub(
                metadata, expected_title, expected_authors, expected_isbns
            )
            info.update(metadata)
            info["identity"] = identity
            info["warnings"] = warnings + identity_warnings
            return identity != "mismatch" and bool(metadata.get("title")), info, "" if identity != "mismatch" else "identity mismatch"
        if fmt == "pdf":
            with path.open("rb") as handle:
                head = handle.read(8)
                handle.seek(max(0, stat.st_size - 4096))
                tail = handle.read()
            if not head.startswith(b"%PDF-") or b"%%EOF" not in tail:
                return False, info, "invalid PDF header or trailer"
            encrypted = False
            carry = b""
            with path.open("rb") as handle:
                while chunk := handle.read(1024 * 1024):
                    if b"/Encrypt" in carry + chunk:
                        encrypted = True
                        break
                    carry = chunk[-16:]
            if encrypted:
                return False, info, "encrypted/DRM PDF is not accepted"
            info["identity"] = "source_metadata_only" if expected_title else "structure_only"
            info["warnings"] = ["PDF identity relies on source metadata; no OPF is available"]
            return True, info, ""
        return False, info, f"unsupported format: {fmt}"
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as exc:
        return False, {}, clean_remote(str(exc), 220)


def unique_target(outdir: Path, stem: str, fmt: str) -> Path:
    base = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", " ", stem)
    base = re.sub(r"\s+", " ", base).strip(" .")[:140] or "ebook"
    while len(base.encode("utf-8")) > 180:
        base = base[:-1]
    for index in range(0, 10_000):
        suffix = "" if index == 0 else f" ({index + 1})"
        target = outdir / f"{base}{suffix}.{fmt}"
        if not target.exists() and not target.is_symlink():
            return target
    raise OSError("could not reserve a unique output name")


def download_candidate(
    client: HttpClient,
    candidate: Candidate,
    outdir: Path,
    max_bytes: int,
) -> tuple[bool, dict[str, Any]]:
    outdir.mkdir(parents=True, exist_ok=True)
    if outdir.is_symlink() or not outdir.is_dir():
        return False, {"status": "blocked", "error": "output directory is not a real directory"}
    fd, temp_name = tempfile.mkstemp(prefix=".ebook-download-", suffix=f".{candidate.fmt}.part", dir=outdir)
    temp_path = Path(temp_name)
    os.chmod(temp_path, 0o600)
    sha256 = hashlib.sha256()
    md5 = hashlib.md5(usedforsecurity=False)
    bytes_written = 0
    try:
        with client.open(
            candidate.download_url,
            candidate.allowed_hosts,
            "application/epub+zip, application/pdf, application/octet-stream",
        ) as response, os.fdopen(fd, "wb", closefd=True) as output:
            fd = -1
            content_type = response.headers.get_content_type().lower()
            if content_type in {"text/html", "text/plain", "application/vnd.adobe.adept+xml"}:
                raise ParseError(f"download returned {content_type}")
            length = response.headers.get("Content-Length")
            if length and length.isdigit() and int(length) > max_bytes:
                raise SizeLimitError(f"file exceeds {max_bytes} bytes")
            deadline = time.monotonic() + max(60.0, client.timeout * 6)
            while True:
                if time.monotonic() > deadline:
                    raise FetchError("download wall-clock timeout")
                chunk = response.read(128 * 1024)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    raise SizeLimitError(f"file exceeds {max_bytes} bytes")
                output.write(chunk)
                sha256.update(chunk)
                md5.update(chunk)
            output.flush()
            os.fsync(output.fileno())
        if candidate.expected_size and bytes_written != candidate.expected_size:
            raise ParseError(f"size mismatch: expected {candidate.expected_size}, got {bytes_written}")
        if candidate.expected_md5 and md5.hexdigest() != candidate.expected_md5:
            raise ParseError("source MD5 mismatch")
        verified, verification, error = verify_ebook(
            temp_path,
            candidate.fmt,
            expected_title=candidate.title,
            expected_authors=candidate.authors,
            expected_isbns=candidate.isbns,
            max_bytes=max_bytes,
        )
        if not verified or verification.get("identity") not in {"matched", "source_metadata_only"}:
            return False, {"status": "verify_failed", "error": error or "identity not confirmed", "verification": verification}
        author = candidate.authors[0] if candidate.authors else "Unknown author"
        target_stem = f"{candidate.title} - {author}"
        target = unique_target(outdir, target_stem, candidate.fmt)
        while True:
            try:
                os.link(temp_path, target)
                break
            except FileExistsError:
                target = unique_target(outdir, target_stem, candidate.fmt)
        try:
            directory_fd = os.open(outdir, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
        temp_path.unlink()
        verification["sha256"] = sha256.hexdigest()
        return True, {
            "status": "downloaded",
            "path": str(target.resolve()),
            "candidate": candidate.public_dict(),
            "verification": verification,
        }
    except FetchError as exc:
        return False, {"status": exc.status, "error": clean_remote(str(exc), 220)}
    except (OSError, ValueError) as exc:
        return False, {"status": "download_error", "error": clean_remote(str(exc), 220)}
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass


def iter_local_files(root: Path) -> Iterable[Path]:
    if root.name == "Downloads":
        try:
            yield from root.iterdir()
        except OSError:
            return
        return
    for current, directories, files in os.walk(root, followlinks=False, onerror=lambda _error: None):
        current_path = Path(current)
        directories[:] = [name for name in directories if not (current_path / name).is_symlink()]
        for name in files:
            yield current_path / name


def find_existing(
    roots: list[Path],
    query: str,
    author: str,
    isbn: str,
    epub_only: bool,
    max_bytes: int,
) -> Optional[dict[str, Any]]:
    seen: set[Path] = set()
    inspected = 0
    for root in roots:
        root = root.expanduser()
        if not root.exists() or root.is_symlink() or not root.is_dir():
            continue
        for path in iter_local_files(root):
            if inspected >= 5000:
                return None
            if not path.is_file() or path.is_symlink() or path in seen:
                continue
            fmt = path.suffix.lower().lstrip(".")
            if fmt not in ({"epub"} if epub_only else {"epub", "pdf"}):
                continue
            seen.add(path)
            inspected += 1
            filename_score = text_similarity(query, local_name(path)) if query else 0.0
            if query and filename_score < 0.35 and not isbn:
                continue
            ok, info, _ = verify_ebook(
                path,
                fmt,
                expected_title=query if fmt == "epub" else "",
                expected_authors=[author] if author and fmt == "epub" else [],
                expected_isbns=[isbn] if isbn and fmt == "epub" else [],
                max_bytes=max_bytes,
            )
            if ok and info.get("identity") == "matched":
                return {"stage": "existing", "path": str(path.resolve()), "verification": info}
    return None


def manual_options(query: str, author: str, isbn: str) -> list[dict[str, str]]:
    term = " ".join(v for v in (query, author, isbn) if v).strip()
    encoded = urllib.parse.quote_plus(term)
    return [
        {"kind": "public_domain", "label": "Project Gutenberg", "url": f"https://www.gutenberg.org/ebooks/search/?query={encoded}"},
        {"kind": "open_access", "label": "OAPEN", "url": f"https://library.oapen.org/discover?query={encoded}"},
        {"kind": "open_access_discovery", "label": "DOAB", "url": f"https://directory.doabooks.org/discover?query={encoded}"},
        {"kind": "borrow_or_public", "label": "Open Library", "url": f"https://openlibrary.org/search?q={encoded}"},
        {"kind": "preview_or_public", "label": "Google Books", "url": f"https://books.google.com/books?q={encoded}"},
        {"kind": "library_catalog", "label": "WorldCat", "url": f"https://search.worldcat.org/search?q={encoded}"},
        {"kind": "publisher_search", "label": "Publisher/author official site", "url": f"https://www.google.com/search?q={urllib.parse.quote_plus(term + ' official publisher ebook')}"},
    ]


def run_sources(
    client: HttpClient,
    names: list[str],
    query: str,
    author: str,
    isbn: str,
    include_pdf: bool,
    api_key: str,
) -> list[SourceOutcome]:
    jobs = {
        "gutenberg": lambda: search_gutenberg(client, query, author)
        if query
        else ([], "skipped: Gutendex has no ISBN field"),
        "oapen": lambda: search_oapen(client, query, author, isbn),
        "openlibrary": lambda: search_openlibrary(client, query, author, isbn, include_pdf),
        "googlebooks": lambda: search_googlebooks(client, api_key, query, author, isbn, include_pdf),
    }
    outcomes: list[SourceOutcome] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(names))) as pool:
        future_map = {pool.submit(timed_source, name, jobs[name]): name for name in names}
        for future in concurrent.futures.as_completed(future_map):
            outcomes.append(future.result())
    return sorted(outcomes, key=lambda value: names.index(value.source))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", help="book title or title-like query")
    parser.add_argument("--author", default="")
    parser.add_argument("--isbn", default="")
    parser.add_argument("--year", type=int)
    parser.add_argument("--publisher", default="")
    parser.add_argument("--language", default="")
    parser.add_argument("--out", default="~/Downloads")
    parser.add_argument("--library-dir", action="append", default=[])
    parser.add_argument("--source", action="append", choices=("gutenberg", "oapen", "openlibrary", "googlebooks"))
    parser.add_argument("--google-books-key-file", metavar="PATH")
    parser.add_argument("--contact-email", default="")
    parser.add_argument("--epub-only", action="store_true")
    parser.add_argument("--search-only", action="store_true")
    parser.add_argument("--metadata-only", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--verify", metavar="PATH")
    parser.add_argument("--max-size-mb", type=int, default=200)
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--limit", type=int, default=12, help="ranked candidates to retain")
    return parser


def emit(payload: dict[str, Any]) -> None:
    payload.setdefault("schema_version", 1)
    payload.setdefault("remote_metadata_trust", REMOTE_DATA_NOTICE)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    query = clean_remote(args.query, 300)
    author = clean_remote(args.author, 200)
    isbn = normalize_isbn(args.isbn)
    if args.isbn and not valid_isbn(args.isbn):
        emit({"ok": False, "stage": "input", "status": "invalid_input", "error": "invalid ISBN checksum"})
        return 4
    if not query and not isbn and not args.verify:
        emit({"ok": False, "stage": "input", "status": "invalid_input", "error": "provide a title, ISBN, or --verify path"})
        return 4
    if args.max_size_mb < 1 or args.max_size_mb > 2048 or args.timeout <= 0 or args.limit < 1:
        emit({"ok": False, "stage": "input", "status": "invalid_input", "error": "invalid limit, timeout, or size bound"})
        return 4

    if args.verify:
        path = Path(args.verify).expanduser()
        fmt = path.suffix.lower().lstrip(".")
        ok, info, error = verify_ebook(
            path,
            fmt,
            expected_title=query,
            expected_authors=[author] if author else [],
            expected_isbns=[isbn] if isbn else [],
            max_bytes=args.max_size_mb * 1024 * 1024,
        )
        emit({"ok": ok, "stage": "verified" if ok else "verify", "status": "ok" if ok else "verify_failed", "path": str(path), "verification": info, "error": error or None})
        return 0 if ok else 2

    outdir = Path(args.out).expanduser()
    local_roots = [outdir] + [Path(value).expanduser() for value in args.library_dir]
    existing = find_existing(
        local_roots,
        query,
        author,
        isbn,
        args.epub_only,
        args.max_size_mb * 1024 * 1024,
    )
    if existing:
        emit({"ok": True, **existing, "status": "ok", "sources": [{"source": "local", "status": "ok"}]})
        return 0
    if args.offline:
        emit({"ok": False, "stage": "search", "status": "no_match", "sources": [{"source": "local", "status": "no_match"}], "manual_options": []})
        return 3

    contact = clean_remote(args.contact_email, 120)
    api_key = ""
    if args.google_books_key_file:
        try:
            api_key = read_key_file(args.google_books_key_file)
        except (OSError, UnicodeError, ValueError) as exc:
            emit({"ok": False, "stage": "input", "status": "invalid_input", "error": clean_remote(str(exc), 180)})
            return 4
    client = HttpClient(args.timeout, contact)
    source_names = args.source or ["gutenberg", "oapen", "openlibrary", "googlebooks"]

    if args.metadata_only:
        records, attempts = resolve_metadata(client, api_key, query, author, isbn)
        emit(
            {
                "ok": bool(records),
                "stage": "metadata",
                "status": "ok" if records else "no_match",
                "metadata": [record.public_dict() for record in records],
                "metadata_sources": attempts,
                "manual_options": manual_options(query, author, isbn),
            }
        )
        return 0 if records else 3

    outcomes = run_sources(client, source_names, query, author, isbn, not args.epub_only, api_key)
    candidates = [candidate for outcome in outcomes for candidate in outcome.candidates]
    records: list[MetadataRecord] = []
    metadata_attempts: list[dict[str, Any]] = []
    accepted_queries = [query] if query else []

    if not candidates and query:
        records, metadata_attempts = resolve_metadata(client, api_key, query, author, isbn)
        canonical = []
        for record in records[:2]:
            if record.score >= 15 and normalize_text(record.title) != normalize_text(query):
                canonical.append(record)
                accepted_queries.append(record.title)
        retry_sources = [name for name in source_names if name in {"gutenberg", "oapen"}]
        for record in canonical:
            retry_author = record.authors[0] if record.authors else author
            retry = run_sources(client, retry_sources, record.title, retry_author, isbn, not args.epub_only, api_key)
            for outcome in retry:
                outcome.source = f"{outcome.source}:canonical_retry"
                outcomes.append(outcome)
                candidates.extend(outcome.candidates)

    ranked: list[Candidate] = []
    for candidate in candidates:
        score = score_candidate(
            candidate,
            accepted_queries,
            author,
            isbn,
            args.year,
            clean_remote(args.publisher, 200),
            clean_remote(args.language, 20),
        )
        if score is not None:
            candidate.score = score
            ranked.append(candidate)
    ranked.sort(key=lambda value: (-value.score, 0 if value.fmt == "epub" else 1, value.source))
    ranked = ranked[: args.limit]

    common = {
        "sources": [outcome.public_dict() for outcome in outcomes],
        "metadata": [record.public_dict() for record in records],
        "metadata_sources": metadata_attempts,
        "candidates": [candidate.public_dict() for candidate in ranked],
        "manual_options": manual_options(query, author, isbn),
    }
    if args.search_only:
        emit({"ok": bool(ranked), "stage": "search", "status": "ok" if ranked else "no_match", **common})
        return 0 if ranked else 3

    download_attempts = []
    for candidate in ranked:
        ok, result = download_candidate(client, candidate, outdir, args.max_size_mb * 1024 * 1024)
        download_attempts.append(
            {
                "source": candidate.source,
                "identifier": candidate.identifier,
                "format": candidate.fmt,
                "status": result.get("status"),
                "error": result.get("error"),
            }
        )
        if ok:
            emit({"ok": True, "stage": "downloaded", **result, "download_attempts": download_attempts, **common})
            return 0

    if ranked:
        emit({"ok": False, "stage": "download", "status": "all_downloads_failed", "download_attempts": download_attempts, **common})
        return 2

    worked = any(outcome.status in {"ok", "no_match"} for outcome in outcomes)
    status = "no_match" if worked else "all_sources_unavailable"
    emit({"ok": False, "stage": "search", "status": status, **common})
    return 3 if worked else 5


if __name__ == "__main__":
    sys.exit(main())
