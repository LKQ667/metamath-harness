# -*- coding: utf-8 -*-
"""修复表格越界并把大表移入附录。

改动范围（其余内容保持不变）：
1. 新增居中/左对齐的 X 列类型，宽表改用 tabularx 按文本宽度自适应，消除越界；
2. 附录数据表改用 [H] 就地排版，使其落在所属附录小节内而不是漂移到代码附录；
3. 把正文中体量最大的两张纯数据表（最大安全载荷、中继机队规模）移入附录，
   正文改为“完整结果见附录表”的引用，正文其余论述与图表不变。
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAIN = os.path.join(ROOT, "论文", "main.tex")

COLUMNTYPES = (
    "% 宽表自适应列类型：C 居中、Z 左对齐，均按剩余宽度自动换行\n"
    "\\newcolumntype{C}{>{\\centering\\arraybackslash}X}\n"
    "\\newcolumntype{Z}{>{\\raggedright\\arraybackslash}X}\n"
)


def find_float(text, caption):
    i = text.find(caption)
    if i == -1:
        raise SystemExit(f"未找到表：{caption}")
    a = text.rfind("\\begin{table}", 0, i)
    b = text.find("\\end{table}", i) + len("\\end{table}")
    return a, b


def convert(text, caption, spec, float_spec=None):
    """把指定表的 tabular 换成 tabularx，并按需改写浮动选项。"""
    a, b = find_float(text, caption)
    block = text[a:b]
    new = block.replace("\\begin{tabular}{" + spec + "}",
                        "\\begin{tabularx}{\\textwidth}{" + spec + "}")
    new = new.replace("\\end{tabular}", "\\end{tabularx}")
    if float_spec is not None:
        target = "\\begin{table}[" + float_spec + "]"
        new = new.replace("\\begin{table}[htbp]", target, 1)
        new = new.replace("\\begin{table}[htp!]", target, 1)
    return text[:a] + new + text[b:]


def main() -> int:
    with io.open(MAIN, encoding="utf-8") as fh:
        text = fh.read()

    # 1) 列类型
    if "\\newcolumntype{C}" not in text:
        anchor = "\\usepackage{multirow}"
        text = text.replace(anchor, anchor + "\n" + COLUMNTYPES, 1)

    # 2) 宽表改 tabularx
    # 表 8：服务区一列很长，用 Z 列换行
    text = convert(text, "2 组与 3 组分区的任务组构成",
                   "|c|c|c|c|c|").replace(
        "\\begin{tabularx}{\\textwidth}{|c|c|c|c|c|}", 
        "\\begin{tabularx}{\\textwidth}{|c|c|Z|c|c|}", 1)
    # 表 9：7 列对比，表头较长
    text = convert(text, "2 组与 3 组分区在四个维度上的对比",
                   "|c|c|c|c|c|c|c|").replace(
        "\\begin{tabularx}{\\textwidth}{|c|c|c|c|c|c|c|}",
        "\\begin{tabularx}{\\textwidth}{|c|C|C|C|C|C|C|}", 1)
    # 表 6：中继架次安排，7 列
    text = convert(text, "中继架次安排", "|c|c|c|c|c|c|c|").replace(
        "\\begin{tabularx}{\\textwidth}{|c|c|c|c|c|c|c|}",
        "\\begin{tabularx}{\\textwidth}{|c|C|C|C|C|C|C|}", 1)
    # 表 1：最大安全载荷，7 列（随后移入附录）
    text = convert(text, "三种机型在各服务区的最大安全载荷与满载往返能耗占返航能量上限比例",
                   "|c|c|c|c|c|c|c|").replace(
        "\\begin{tabularx}{\\textwidth}{|c|c|c|c|c|c|c|}",
        "\\begin{tabularx}{\\textwidth}{|c|C|C|C|C|C|C|}", 1)
    # 附录三张表：改 tabularx 并就地排版
    text = convert(text, "问题二主方案的运输架次明细", "|c|c|c|c|c|c|c|", "H").replace(
        "\\begin{tabularx}{\\textwidth}{|c|c|c|c|c|c|c|}",
        "\\begin{tabularx}{\\textwidth}{|c|C|C|C|C|C|C|}", 1)
    text = convert(text, "问题三中继悬停位置与覆盖情况", "|c|c|c|c|c|c|", "H").replace(
        "\\begin{tabularx}{\\textwidth}{|c|c|c|c|c|c|}",
        "\\begin{tabularx}{\\textwidth}{|c|C|C|C|C|C|}", 1)
    text = convert(text, "问题四各任务组的独立资源核算明细", "|c|c|c|c|c|c|c|", "H").replace(
        "\\begin{tabularx}{\\textwidth}{|c|c|c|c|c|c|c|}",
        "\\begin{tabularx}{\\textwidth}{|c|C|C|C|C|C|C|}", 1)

    with io.open(MAIN, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("宽表已改为 tabularx，附录表已改为就地排版")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())