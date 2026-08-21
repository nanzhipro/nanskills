#!/usr/bin/env bash
# shoot_atlas.sh — 架构大图逐视图截图(需本机 Chrome)
# 用法: bash shoot_atlas.sh <atlas_dir> [port] [views-csv] [entry.html]
#       bash shoot_atlas.sh <atlas_dir> --stop
#   atlas_dir  工程目录(含入口 html 与 data.js)。必须传绝对路径或真实目录名,
#              不能传 '.'(basename 用于 URL 前缀与 serves_dir 探测,传 '.' 会
#              变成根路径 → 截图全是 404 页)
#   port       本地 HTTP 端口,默认 4311;被占用且不服务本目录时自动顺延探测
#   views-csv  逗号分隔视图 id 或 hash 片段,默认 overview;支持 flows/<flowId>
#   entry.html 入口文件名;缺省取目录内第一个不含 Standalone 的 .html
#   --stop     停止上次为本目录启动的 server(读 .atlas-server.pid)
# 环境变量:
#   CHROME     Chrome 可执行文件路径
#   WINDOW     窗口尺寸,默认 1680,1050;目检细节可 WINDOW=3100,1800
#   NOLEGEND=1 截图时收起图例面板(URL 带 ?legend=0),避免遮挡左下角节点
#   THEME     截图主题(light/dark/paper/sepia),默认 light;产物文件名带 -<theme> 后缀
# 产物: <atlas_dir>/_shots/<view>.png(<THEME> 时 <view>-<theme>.png)
#
# server 治理:先扫描端口段复用「已在服务本目录」的 server;确需新起时用
# exec 让 PID 即 python 本身并记入 <atlas_dir>/.atlas-server.pid——历史版本
# 每跑一次就留一批僵尸 server,会把整个端口段占满。
set -euo pipefail

DIR="${1:?用法: shoot_atlas.sh <atlas_dir> [port] [views-csv] [entry.html] | shoot_atlas.sh <atlas_dir> --stop}"
PORT="${2:-4311}"
VIEWS="${3:-overview}"
ENTRY="${4:-}"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
WINDOW="${WINDOW:-1680,1050}"
PIDFILE="$DIR/.atlas-server.pid"

[ -x "$CHROME" ] || { echo "找不到 Chrome,可用 CHROME=/path/to/chrome 指定" >&2; exit 2; }

# ---- --stop:清掉本目录记录的 server ----
if [ "$PORT" = "--stop" ]; then
  if [ -f "$PIDFILE" ]; then
    read -r SPID SPORT < "$PIDFILE" || true
    if [ -n "${SPID:-}" ] && kill -0 "$SPID" 2>/dev/null; then
      kill "$SPID" && echo "已停止 server pid=$SPID (端口 $SPORT)"
    else
      echo "pid=$SPID 已不在运行"
    fi
    rm -f "$PIDFILE"
  else
    echo "无 $PIDFILE —— 本目录没有记录中的 server"
  fi
  exit 0
fi

if [ -z "$ENTRY" ]; then
  ENTRY="$(ls "$DIR" | grep '\.html$' | grep -v Standalone | head -1)"
fi
[ -n "$ENTRY" ] || { echo "目录内没有入口 html" >&2; exit 2; }

# 判定用内容标记(data.js 里的 ATLAS),不看 HTTP 状态码——本机可能有 catch-all 代理
# 对任意端口/路径都回 200/502(实测会骗过"端口被占"探测,把每个端口都误判为占用)
# 用 127.0.0.1 而非 localhost:规避 IPv6 解析差异,直连本机 server
serves_dir() { local body; body="$(curl -sf --max-time 3 "http://127.0.0.1:$1/$(basename "$DIR")/data.js" 2>/dev/null)" || return 1; [[ "$body" == *ATLAS* ]]; }
# 注意:探测绝不能写成管道 grep——pipefail 下 grep -q 命中即退出,上游
# (curl 或 echo)收 SIGPIPE(exit 23/141),探测永远为假(实测 macOS/curl 8.x 必现)。

# ---- 第一遍:复用已在服务本目录的端口(包括本脚本此前启动并记录的) ----
FOUND=""
for p in $(seq "$PORT" $((PORT + 19))); do
  if serves_dir "$p"; then FOUND="$p"; break; fi
done

# ---- 第二遍:都没有则新起;exec 使 $! 即 python 本身的 PID ----
if [ -z "$FOUND" ]; then
  for p in $(seq "$PORT" $((PORT + 19))); do
    (cd "$(dirname "$DIR")" && exec python3 -m http.server "$p") >/dev/null 2>&1 </dev/null &
    NEWPID=$!
    # 就绪重试:机器负载高时 python 绑定+首响可超过 1s,判负前多等几拍
    for _ in 1 2 3 4 5 6; do
      sleep 0.5
      serves_dir "$p" && break
    done
    if serves_dir "$p"; then
      FOUND="$p"
      echo "$NEWPID $p" > "$PIDFILE"
      break
    fi
    # 端口被别人占着(bind 失败,子进程已退出)或服务内容不对:收回子进程再试下一个
    kill "$NEWPID" 2>/dev/null || true
    wait "$NEWPID" 2>/dev/null || true
  done
fi
[ -n "$FOUND" ] || { echo "无可用端口(自 $PORT 起试了 20 个;可换个起始端口或先 --stop 清理)" >&2; exit 2; }
[ "$FOUND" != "$PORT" ] && echo "提示: 端口 $PORT 不可用或不服务本目录,改用 $FOUND"
PORT="$FOUND"

BASE="http://localhost:$PORT/$(basename "$DIR")"
ENC_ENTRY="$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$ENTRY")"
mkdir -p "$DIR/_shots"

# NOLEGEND=1 时在 hash 里带参数,让引擎收起图例面板(模板已支持);
# THEME 非空时追加 ?theme=<name>(模板已支持)
QPARAMS=""
[ "${NOLEGEND:-}" = "1" ] && QPARAMS="legend=0"
[ -n "${THEME:-}" ] && QPARAMS="${QPARAMS:+$QPARAMS&}theme=$THEME"
QSTR=""
[ -n "$QPARAMS" ] && QSTR="?$QPARAMS"

IFS=',' read -ra VV <<< "$VIEWS"
for v in "${VV[@]}"; do
  safe="$(echo "$v" | tr '/' '_')"
  [ -n "${THEME:-}" ] && safe="${safe}-${THEME}"
  # stdout 也必须丢弃:Chrome helper 进程会继承 stdout 占住管道,导致脚本截完不退出
  "$CHROME" --headless --disable-gpu --hide-scrollbars \
    --window-size="$WINDOW" --virtual-time-budget=4000 \
    --screenshot="$DIR/_shots/$safe.png" "$BASE/$ENC_ENTRY#/$v$QSTR" >/dev/null 2>&1
  echo "shot: $DIR/_shots/$safe.png"
done
echo "完成。请逐张读图目检(重叠/孤立/遮挡/组框包含/黑底无字)。"
