# AGENTS.md — nanskills Constitution

This file is the **constitution** of this repository. It defines binding rules for every skill added, modified, or removed here. When this file conflicts with other instructions, this file wins.

## Rule 1 — Skill Naming (binding)

- Every skill directory MUST use the `nan-` prefix: `skills/nan-<name>/`.
- The `name` in the SKILL.md frontmatter MUST match the directory name.
- A skill without the `nan-` prefix MUST NOT be added, committed, or pushed.
- **Violation reporting is mandatory**: before `git add` / commit / push, run `scripts/check_skill_naming.sh`. If it fails, report the error to the user and remind them to rename the offending skill to `nan-<name>` before proceeding. Never silently commit a non-conforming skill.

## Rule 2 — Anthropic Skill Best Practices (binding)

Every `SKILL.md` MUST follow the Anthropic agent-skill conventions:

- YAML frontmatter: `name`, `description`, `version`, `license`, `platforms`, `metadata`.
- The `description` defines when the skill triggers ("Use when ..."). Keep the trigger self-contained in the first ~57 characters.
- Body structure: step-by-step Workflow, decision trees, hard rules, **Pitfalls**, and **Verification** steps.
- Verification is mandatory: every downloaded file, API response, or generated artifact must be verified before reporting success.
- Prefer LLM semantic reasoning over rigid hard rules; merge redundant rules; never state rules that contradict each other.
- Document runtime dependencies and graceful degradation inside the skill (no hidden requirements).

## Rule 3 — Componentized Design (binding)

Each skill is a self-contained component under `skills/<name>/`:

```
skills/<name>/
├── SKILL.md        # specification: frontmatter + workflow + pitfalls + verification
├── scripts/        # bundled automation (Python / shell / Node)
├── references/     # implementation notes, pitfalls, case studies
├── assets/         # templates and static resources (optional)
├── README.md       # human-facing docs (optional)
└── VERSION         # semantic version (optional)
```

- Skills must not depend on files outside their own directory.
- Runtime knowledge discovered during use MUST be recorded back into the skill's `references/pitfalls.md` (numbered, referenced from SKILL.md).

## Rule 4 — Enforcement

- Run `scripts/check_skill_naming.sh` before any commit or push; a non-zero exit blocks the push until resolved.
- Report violations as errors to the user — do not "fix silently" or skip.
- New failure modes encountered at runtime are skill defects: patch the skill (or its pitfalls) before finishing the task.

## Rule 5 — Legal and Ethical Baseline

- Skills automate workflows; this repository does not host or distribute copyrighted content.
- Include legal disclaimers in README.md and at the top of each SKILL.md.
- Respect robots.txt and rate limits. No DRM circumvention. Users assume legal liability for their own use.

## Repository Overview

**nanskills** is a curated collection of AI agent skills — reusable, self-contained workflows that automate complex multi-step tasks. Skills use the SKILL.md format and work with Claude Code, Codex CLI, Hermes Agent, or any agent framework that supports this format.

### Current Skills

- **nan-ebook-download** (v6.2.0): Multi-source ebook search and download pipeline (libgen → Anna's Archive → VK.com → OceanofPDF). EPUB-first, PDF fallback. Includes proxy auto-detection for GFW users, metadata resolution via Open Library/Douban, and streaming downloads with verification.
- **nan-codebase-architecture-atlas** (v1.0.0): Codebase understanding and architecture visualization. Ontology-driven exploration (entities/relations/data flows/design principles, evidence-backed) → four-layer interactive architecture atlas (panorama → module topology → module internals → data-flow sequence), with layout linting, screenshot review, and a single-file offline build.

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

6. **Fallback chains** — when primary sources fail, define a strict fallback order. Document each source's failure modes in `references/pitfalls.md`.

7. **Cache-first** — before expensive operations (downloads, API calls), check if a valid cached result exists. Use content-based validation, not just file existence.

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

## Platform Notes (macOS)

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
