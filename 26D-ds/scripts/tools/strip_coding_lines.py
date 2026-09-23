# -*- coding: utf-8 -*-
"""从 main.tex 的内联 Python 代码块中去掉编码声明行。

附录代码块内部必须是纯代码，不允许注释行；编码声明行属于注释，
且净化副本 .py 文件本身保留该行不受影响。
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAIN = os.path.join(ROOT, "论文", "main.tex")

BLOCK_RE = re.compile(r"(\\begin\{Python\}\{[^{}]*\}\n)(.*?)(\n\\end\{Python\})", re.DOTALL)
CODING_RE = re.compile(r"^#.*coding[:=].*$")


def main() -> int:
    with io.open(MAIN, encoding="utf-8") as fh:
        text = fh.read()

    removed = 0

    def repl(match):
        nonlocal removed
        lines = match.group(2).splitlines()
        kept = [ln for ln in lines if not CODING_RE.match(ln.strip())]
        removed += len(lines) - len(kept)
        return match.group(1) + "\n".join(kept) + match.group(3)

    new_text, blocks = BLOCK_RE.subn(repl, text)
    if blocks == 0:
        raise SystemExit("未匹配到内联 Python 代码块")
    with io.open(MAIN, "w", encoding="utf-8") as fh:
        fh.write(new_text)
    print(f"处理 {blocks} 个代码块，移除 {removed} 行编码声明")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())