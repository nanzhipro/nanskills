#!/usr/bin/env python3
"""extract_standalone.py — 从单文件离线版还原多文件源工程(Atlas.html / app.js / data.js)

用法: python3 extract_standalone.py <standalone.html> [<输出目录>]
默认输出到 standalone 所在目录;输出目录已有同名文件时直接覆盖,请先备份。

规则: 只做恢复。前提是 standalone 由本技能的 build_standalone.py 生成且未被手改
(内联格式为 <script src="X.js"></script> → <script>\\n内容\\n</script>,内容原样嵌入)。
若内联内容疑似含 </script> 序列导致正则截断,字节守恒校验不成立,脚本会中止并提示手工处理,
绝不产出半截文件。
"""
import os
import re
import sys


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("用法: extract_standalone.py <standalone.html> [<输出目录>]")
    src_path = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(src_path))
    html = open(src_path, encoding="utf-8").read()

    blocks = re.findall(r"<script>\n(.*?)\n</script>", html, re.S)
    data_blocks = [b for b in blocks if "const ATLAS" in b]
    app_blocks = [b for b in blocks if "const ATLAS" not in b]
    if len(data_blocks) != 1 or len(app_blocks) != 1:
        sys.exit(
            f"识别失败: 找到 {len(blocks)} 个内联脚本块 (data={len(data_blocks)} app={len(app_blocks)});"
            "文件不是本技能生成的 standalone,或已被手改。"
        )
    data, app = data_blocks[0], app_blocks[0]

    restored = html.replace(f"<script>\n{data}\n</script>", '<script src="data.js"></script>')
    restored = restored.replace(f"<script>\n{app}\n</script>", '<script src="app.js"></script>')

    # 字节守恒: 还原结果必须等于 原文件 − 两个内联块 + 两个 src 标签 − 两套包装。
    # 任何一处截断都会破坏等式,从而拒绝产出。
    wrapper = len("<script>\n") + len("\n</script>")
    tag_data = len('<script src="data.js"></script>')
    tag_app = len('<script src="app.js"></script>')
    expect = len(html) - len(data) - len(app) + tag_data + tag_app - 2 * wrapper
    if (
        len(restored) != expect
        or '<script src="data.js"></script>' not in restored
        or '<script src="app.js"></script>' not in restored
    ):
        sys.exit(
            "内联内容疑似含 </script> 序列导致截断,自动恢复不可靠;"
            "请人工切出两个 <script> 块,或从 git/备份找回源工程。"
        )

    os.makedirs(out_dir, exist_ok=True)
    open(os.path.join(out_dir, "data.js"), "w", encoding="utf-8").write(data)
    open(os.path.join(out_dir, "app.js"), "w", encoding="utf-8").write(app)
    open(os.path.join(out_dir, "Atlas.html"), "w", encoding="utf-8").write(restored)
    print(
        f"restored: Atlas.html={len(restored)}B data.js={len(data)}B app.js={len(app)}B -> {out_dir}"
    )
    print("恢复后先跑 validate_atlas_data.js,再用 build_standalone.py 往返比对,确认无误再删 standalone。")


if __name__ == "__main__":
    main()
