# -*- coding: utf-8 -*-
"""把剩余的定宽表（中继机队规模）也改为 tabularx 自适应宽度。"""
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAIN = os.path.join(ROOT, "论文", "main.tex")

CAP = "中继机队规模对联合调度可行性的影响"


def main() -> int:
    with io.open(MAIN, encoding="utf-8") as fh:
        text = fh.read()
    i = text.find(CAP)
    if i == -1:
        raise SystemExit("未找到目标表")
    a = text.rfind("\\begin{table}", 0, i)
    b = text.find("\\end{table}", i) + len("\\end{table}")
    block = text[a:b]
    if "tabularx" in block:
        print("该表已是 tabularx，无需修改")
        return 0
    new = block.replace("\\begin{tabular}{|c|c|c|c|c|c|}",
                        "\\begin{tabularx}{\\textwidth}{|c|C|C|C|C|C|}")
    new = new.replace("\\end{tabular}", "\\end{tabularx}")
    with io.open(MAIN, "w", encoding="utf-8") as fh:
        fh.write(text[:a] + new + text[b:])
    print("已改为 tabularx 自适应宽度")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())