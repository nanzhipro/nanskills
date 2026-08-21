#!/usr/bin/env bash
# check_skill_naming.sh — enforce the nan- naming convention (AGENTS.md Rule 1).
# Scans skills/ and reports any directory that does not use the nan- prefix.
# Exit code 0 = all conform; 1 = violations found (blocks commit/push).
set -u

root="$(cd "$(dirname "$0")/.." && pwd)"
violations=0

for d in "$root"/skills/*/; do
    [ -d "$d" ] || continue
    name="$(basename "$d")"
    case "$name" in
        nan-*) ;;
        *)
            echo "ERROR: skill '${name}' violates the naming convention: expected 'skills/nan-<name>/' (AGENTS.md Rule 1)." >&2
            violations=$((violations + 1))
            ;;
    esac
done

if [ "$violations" -gt 0 ]; then
    echo "FAIL: ${violations} skill(s) missing the required 'nan-' prefix. Rename them before committing." >&2
    exit 1
fi

echo "OK: all skills use the 'nan-' prefix."
