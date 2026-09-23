# -*- coding: utf-8 -*-
"""把 论文/附录代码/ 下的净化副本同步回 main.tex 中已内联的 Python 代码块。

在源码或净化副本更新后运行，保持论文内联代码与净化副本一致。
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAIN = os.path.join(ROOT, "论文", "main.tex")
CODE_DIR = os.path.join(ROOT, "论文", "附录代码")


def main() -> int:
    with io.open(MAIN, encoding="utf-8") as fh:
        text = fh.read()
    updated = 0
    for name in sorted(os.listdir(CODE_DIR)):
        if not name.endswith(".py"):
            continue
        path = os.path.join(CODE_DIR, name)
        with io.open(path, encoding="utf-8") as fh:
            body = fh.read().rstrip("\n")
        texname = name.replace("_", "\\_")
        pattern = re.compile(
            r"(\\begin\{Python\}\{" + re.escape(texname) + r"\}\n)(.*?)(\n\\end\{Python\})",
            re.DOTALL)
        new_text, n = pattern.subn(lambda m: m.group(1) + body + m.group(3), text)
        if n:
            text = new_text
            updated += n
            print(f"已同步 {name}（{n} 个代码块）")
    with io.open(MAIN, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"共更新 {updated} 个代码块")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())