# -*- coding: utf-8 -*-
"""把 main.tex 的符号表由 tabularx 改为 longtable 版本。

依据模板 main.tex 的说明：符号内容实际超过一页时改用 longtable 自动跨页并重复表头，
进入前保存 table 计数、结束后恢复，保证符号表不占用正式结果表编号。
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAIN = os.path.join(ROOT, "论文", "main.tex")

HEAD = r"""\renewcommand\arraystretch{1.2}
\newcolumntype{P}[1]{>{\centering\arraybackslash}p{#1}}
% 符号内容超过一页，按模板说明改用 longtable：自动跨页并重复表头，
% 进入前保存 table 计数、结束后恢复，使符号表不占用正式结果表编号。
\newcounter{huaweisymbolsavetable}
\setcounter{huaweisymbolsavetable}{\value{table}}
\begin{longtable}{|P{1.6cm}|>{\raggedright\arraybackslash}p{\dimexpr0.9\textwidth-1.6cm-4\tabcolsep-3\arrayrulewidth\relax}|}
  \hline
  符号    &   \quad 意义 \\
  \hline
  \endfirsthead
  \hline
  符号    &   \quad 意义（续） \\
  \hline
  \endhead
"""
TAIL = r"""\end{longtable}
\setcounter{table}{\value{huaweisymbolsavetable}}
"""


def main() -> int:
    with io.open(MAIN, encoding="utf-8") as fh:
        text = fh.read()
    start = text.find(r"\noindent\begin{tabularx}{0.9\textwidth}{|P{1.6cm}|L|}")
    if start == -1:
        print("未找到符号表 tabularx 块（可能已转换）")
        return 0
    end = text.find(r"\end{tabularx}", start)
    if end == -1:
        raise SystemExit("符号表缺少结束标记")
    end += len(r"\end{tabularx}")
    block = text[start:end]
    # 取出数据行：形如 "  $x$  &  说明    \\"
    rows = re.findall(r"^\s*(.+?)\s*&\s*(.+?)\s*\\\\\s*$", block, re.MULTILINE)
    rows = [(a.strip(), b.strip()) for a, b in rows if a.strip() and "符号" not in a]
    body = "\n".join(f"  {a}  &  {b}    \\\\\n  \\hline" for a, b in rows)
    new_block = HEAD + body + "\n" + TAIL
    text = text[:start] + new_block + text[end:]
    # 同时移除已不再使用的 L 列定义
    text = text.replace(r"\newcolumntype{L}{>{\quad}X}" + "\n", "")
    with io.open(MAIN, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"符号表已转换为 longtable，共 {len(rows)} 行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())