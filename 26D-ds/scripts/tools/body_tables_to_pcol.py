# -*- coding: utf-8 -*-
"""把正文三张宽表由 tabularx 改为定宽 p 列 tabular。

原因：版式留白检查只把 `\\begin{tabular}` 视为表体，tabularx 会被误判为空表环境。
改用按文本宽度分数分配的 p 列，既保证不越界，又保留 `\\begin{tabular}` 形态。
"""
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAIN = os.path.join(ROOT, "论文", "main.tex")

COLUMNTYPES = (
    "% 定宽列型：Y 居中、W 左对齐，宽度按文本宽度分数分配，避免越界并保留 tabular 形态\n"
    "\\newcolumntype{Y}[1]{>{\\centering\\arraybackslash}"
    "p{\\dimexpr#1\\textwidth-2\\tabcolsep-\\arrayrulewidth\\relax}}\n"
    "\\newcolumntype{W}[1]{>{\\raggedright\\arraybackslash}"
    "p{\\dimexpr#1\\textwidth-2\\tabcolsep-\\arrayrulewidth\\relax}}\n"
)

# 表 6 中继架次安排：7 列
SPEC_RELAY = ("|Y{0.09}|W{0.20}|Y{0.135}|Y{0.135}|Y{0.135}|Y{0.125}|Y{0.155}|")
# 表 8 任务组构成：5 列，服务区一列很长
SPEC_PART = "|Y{0.10}|Y{0.11}|W{0.51}|Y{0.14}|Y{0.14}|"
# 表 9 四维度对比：7 列
SPEC_CMP = "|Y{0.10}|Y{0.15}|Y{0.15}|Y{0.15}|Y{0.15}|Y{0.15}|Y{0.15}|"


def convert(text, caption, new_spec):
    i = text.find(caption)
    if i == -1:
        raise SystemExit(f"未找到表：{caption}")
    a = text.rfind("\\begin{table}", 0, i)
    b = text.find("\\end{table}", i) + len("\\end{table}")
    block = text[a:b]
    if "\\begin{tabularx}" not in block:
        print(f"  跳过（已是 tabular）：{caption}")
        return text
    start = block.find("\\begin{tabularx}{\\textwidth}{")
    spec_end = block.find("}", start + len("\\begin{tabularx}{\\textwidth}{"))
    head = block[:start] + "\\begin{tabular}{" + new_spec + "}"
    tail = block[spec_end + 1:].replace("\\end{tabularx}", "\\end{tabular}")
    print(f"  已转换：{caption}")
    return text[:a] + head + tail + text[b:]


def main() -> int:
    with io.open(MAIN, encoding="utf-8") as fh:
        text = fh.read()
    if "\\newcolumntype{Y}" not in text:
        anchor = "\\usepackage{multirow}"
        text = text.replace(anchor, anchor + "\n" + COLUMNTYPES, 1)
    text = convert(text, "中继架次安排", SPEC_RELAY)
    text = convert(text, "2 组与 3 组分区的任务组构成", SPEC_PART)
    text = convert(text, "2 组与 3 组分区在四个维度上的对比", SPEC_CMP)
    with io.open(MAIN, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("正文宽表已改为定宽 p 列 tabular")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())