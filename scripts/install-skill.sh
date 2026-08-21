#!/usr/bin/env bash
# install-skill.sh — install a single skill from the GitHub repo without cloning the full repository.
# Usage: install-skill.sh <skill-name> [target-dir]
#   skill-name  MUST start with 'nan-' (AGENTS.md Rule 1)
#   target-dir  defaults to ~/.agents/skills/
# Downloads the repo tarball but extracts only the requested skill directory.
set -euo pipefail

SKILL_NAME="${1:-}"
TARGET_DIR="${2:-$HOME/.agents/skills}"
REPO="nanzhipro/nanskills"
BRANCH="main"
TARBALL="https://codeload.github.com/${REPO}/tar.gz/refs/heads/${BRANCH}"
TOP_DIR="nanskills-${BRANCH}"

if [ -z "$SKILL_NAME" ]; then
    echo "Usage: $0 <skill-name> [target-dir]" >&2
    exit 1
fi

case "$SKILL_NAME" in
    nan-*) ;;
    *) echo "ERROR: skill name must use the 'nan-' prefix (AGENTS.md Rule 1): ${SKILL_NAME}" >&2; exit 1 ;;
esac

echo "Fetching skills/${SKILL_NAME} from ${REPO} (${BRANCH}) ..."
mkdir -p "$TARGET_DIR"
curl -fsSL "$TARBALL" | tar -xz --strip-components=2 -C "$TARGET_DIR" "${TOP_DIR}/skills/${SKILL_NAME}"

if [ ! -f "$TARGET_DIR/${SKILL_NAME}/SKILL.md" ]; then
    echo "ERROR: SKILL.md missing after install; the skill directory was not found in the archive." >&2
    exit 1
fi

echo "Installed: ${TARGET_DIR}/${SKILL_NAME}"
