#!/usr/bin/env bash
# preflight.sh — 架构大图工具链预检:建模前跑一次,缺什么早报,别等截图/交付才发现
# 用法: bash preflight.sh [atlas_dir]
#   atlas_dir 可选:传入工程目录时额外验证其 data.js 可被校验器解析(模板基线)
# 检查项: node(≥18) / python3(≥3.8) / PIL / Chrome / 本技能各脚本语法
# 环境变量: CHROME 自定义 Chrome 路径(与 shoot_atlas.sh 一致)
set -uo pipefail
FAIL=0
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

pass() { echo "PASS  $1"; }
fail() { echo "FAIL  $1"; FAIL=1; }

node -e 'const m = +process.versions.node.split(".")[0]; process.exit(m >= 18 ? 0 : 1)' >/dev/null 2>&1 \
  && pass "node >=18 ($(node -v 2>/dev/null))" || fail "node >=18 (当前 $(node -v 2>/dev/null || echo 缺失))"

python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1 \
  && pass "python3 >=3.8 ($(python3 --version 2>/dev/null | cut -d' ' -f2))" || fail "python3 >=3.8"

python3 -c 'import PIL' >/dev/null 2>&1 \
  && pass "PIL (python3)" || fail "PIL 缺失 -> pip3 install pillow (墨迹覆盖率验证需要)"

CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
[ -x "$CHROME" ] && pass "Chrome ($CHROME)" || fail "Chrome 未找到,设 CHROME=/path/to/chrome"

for s in validate_atlas_data.js lint_atlas_layout.js; do
  node --check "$SKILL_DIR/scripts/$s" >/dev/null 2>&1 \
    && pass "scripts/$s 语法" || fail "scripts/$s 语法错误"
done
for s in build_standalone.py extract_standalone.py; do
  python3 -m py_compile "$SKILL_DIR/scripts/$s" >/dev/null 2>&1 \
    && pass "scripts/$s 语法" || fail "scripts/$s 语法错误"
done
[ -f "$SKILL_DIR/scripts/shoot_atlas.sh" ] && pass "scripts/shoot_atlas.sh 存在" || fail "scripts/shoot_atlas.sh 缺失"

if [ -n "${1:-}" ] && [ -d "$1" ]; then
  node "$SKILL_DIR/scripts/validate_atlas_data.js" "$1/data.js" >/dev/null 2>&1 \
    && pass "data.js 可解析且引用完整" || { echo "WARN  data.js 校验未通过(继续建模前先修)"; FAIL=1; }
fi

[ "$FAIL" = 0 ] && echo "== 全部就绪,开工 ==" || { echo "== 有缺失项,先补齐再开工 =="; exit 1; }
