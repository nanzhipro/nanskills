# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

**nanskills** is a curated collection of AI agent skills — reusable, self-contained workflows that automate complex multi-step tasks. Skills use the SKILL.md format and work with Claude Code, Codex CLI, Hermes Agent, or any agent framework that supports this format.

Each skill lives in `skills/<skill-name>/` with a SKILL.md frontmatter specification, bundled scripts, and reference documentation.

## Architecture

### Skill Structure

```
skills/
└── <skill-name>/
    ├── SKILL.md              # Specification with frontmatter (name, version, triggers)
    ├── scripts/              # Bundled automation scripts (Python, shell)
    └── references/           # Implementation notes, pitfalls, case studies
```

**SKILL.md format:**
- YAML frontmatter: `name`, `description`, `version`, `license`, `platforms`, `metadata`
- Body: step-by-step workflow, decision trees, verification procedures
- The `description` field defines when the skill triggers — be precise about trigger conditions

### Current Skills

- **ebook-download** (v6.2.0): Multi-source ebook search and download pipeline (libgen → Anna's Archive → VK.com → OceanofPDF). EPUB-first, PDF fallback. Includes proxy auto-detection for GFW users, metadata resolution via Open Library/Douban, and streaming downloads with verification.
- **codebase-architecture-atlas** (v1.0.0): Codebase understanding and architecture visualization. Ontology-driven exploration (entities/relations/data flows/design principles, evidence-backed) → four-layer interactive architecture atlas (panorama → module topology → module internals → data-flow sequence), with layout linting, screenshot review, and a single-file offline build. Naming: `nan-` prefix marks original skills; upstream-named skills keep their names.

## Development Guidelines

### Adding or Modifying Skills

1. **SKILL.md is authoritative** — all workflow logic, decision trees, and failure modes live here. Scripts implement the workflow; SKILL.md defines it.

2. **Bundle dependencies** — skills must be self-contained. If a skill needs Python packages (e.g., `cloudscraper`), document the requirement in SKILL.md and handle graceful degradation or auto-installation.

3. **Proxy and network awareness** — for skills that access external services behind GFW, auto-detect system proxy via `networksetup -getsecurewebproxy` and configure `HTTPS_PROXY`/`HTTP_PROXY` before any network calls.

4. **Python runtime portability** — don't hardcode Python paths. Discover the working Python dynamically:
   ```bash
   for py in /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3 \
            /usr/local/bin/python3 /usr/bin/python3 python3; do
       if command -v "$py" >/dev/null 2>&1 && \
          $py -c "import required_package" 2>/dev/null; then
           export SKILL_PYTHON="$py"
           break
       fi
   done
   ```

5. **Background vs foreground execution** — for long-running operations (>2 minutes), use background mode with progress updates. Foreground is acceptable for <10 MB downloads or operations under 5 minutes.

6. **Verification is mandatory** — every downloaded file, API response, or generated artifact must be verified before reporting success. For ebooks: check magic bytes, validate ZIP structure, parse metadata.

7. **Fallback chains** — when primary sources fail, define a strict fallback order. Document each source's failure modes in `references/pitfalls.md`.

8. **Cache-first** — before expensive operations (downloads, API calls), check if a valid cached result exists. Use content-based validation, not just file existence.

### Reference Documentation

Keep `references/` up to date with:
- **pitfalls.md**: numbered list of failure modes and fixes
- **case-study-*.md**: worked examples showing the full pipeline in action
- **url-patterns.md**: canonical URLs, dead mirrors, domain rotation
- **source-and-rights-policy.md**: legal disclaimers, content policy

Update pitfalls when you encounter new failure modes. Number them sequentially and reference by number in SKILL.md.

## Testing Skills

Skills don't have traditional unit tests. Verification happens at runtime:

1. **Dry-run mode** — use `--search-only` or `--probe` flags to test discovery without downloading
2. **Small test cases** — use short, well-known titles with predictable results (e.g., "Thinking Fast Slow Kahneman")
3. **Manual verification** — after automation completes, verify the file on disk matches the requested book

## Legal and Ethical Constraints

This repository automates search and download workflows. It does **not** host, distribute, or provide access to any copyrighted content.

- Include legal disclaimers in README.md and at the top of each SKILL.md
- Skills must respect robots.txt and rate limits
- No DRM circumvention
- Users assume all legal liability for how they use these tools

## Platform Notes

**macOS-specific commands:**
- `networksetup -getsecurewebproxy Wi-Fi` (proxy detection)
- `scutil --proxy` (SOCKS proxy detection)
- `open -a Safari` (does NOT work for file downloads; use terminal tools)

**Python on macOS:**
- Homebrew Python (OpenSSL) preferred over system Python (LibreSSL) for TLS compatibility
- System Python on macOS 13+ may lack `pip`; use `python3 -m pip install --user`

## Common Pitfalls

1. **Don't skip network preparation** — auto-detect proxy and configure env vars before any external calls
2. **Environment variables don't cross foreground→background boundary** — inline discovery in background commands
3. **Browser automation has limits** — Cloudflare iframe challenges cannot be bypassed headlessly; fall back to manual instructions
4. **Process status ≠ file status** — always verify files on disk; processes can hang after writing complete files
5. **libgen session keys are single-use** — never reuse a get.php key; fetch fresh on retry
