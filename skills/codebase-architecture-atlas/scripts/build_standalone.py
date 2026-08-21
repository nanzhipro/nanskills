#!/usr/bin/env python3
"""build_standalone.py — 把多文件工程内联成单文件离线版 HTML
用法: python3 build_standalone.py <atlas_dir> <entry.html>
产物: <atlas_dir>/<entry 去后缀> - Standalone.html
规则: 单文件版只由本脚本生成;要改内容就改源文件再重新生成。
"""
import sys, os, re

def main():
    if len(sys.argv) < 3:
        sys.exit("用法: build_standalone.py <atlas_dir> <entry.html>")
    d, entry = sys.argv[1], sys.argv[2]
    html_path = os.path.join(d, entry)
    html = open(html_path, encoding="utf-8").read()

    for name in ("data.js", "app.js"):
        src = open(os.path.join(d, name), encoding="utf-8").read()
        tag = f'<script src="{name}"></script>'
        if tag not in html:
            sys.exit(f"入口 {entry} 中找不到 {tag} —— 入口结构应与模板一致")
        html = html.replace(tag, "<script>\n" + src + "\n</script>")

    out = os.path.join(d, re.sub(r"\.html$", "", entry) + " - Standalone.html")
    open(out, "w", encoding="utf-8").write(html)
    print(f"standalone: {out} ({os.path.getsize(out)//1024} KB)")

if __name__ == "__main__":
    main()
