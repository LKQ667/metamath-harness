# -*- coding: utf-8 -*-
"""一次性补丁：收紧 main.tex 中 Python 代码环境的字号与边距。

做法：把模板 gmcmthesis.cls 定义的 \\Python 与 \\endPython 两个宏先备份，
再用 \\renewcommand 在原有设置之后追加一条 \\lstset，只改字号与左右边距。
不重定义环境本身，也不新建第二套样式系统。
"""
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAIN = os.path.join(ROOT, "论文", "main.tex")

NEW = r"""% 附录代码排版：备份模板既有的 Python 代码环境宏，在其设置之后追加一条 lstset，
% 只收紧字号与左右边距以缓解长行折行造成的版面稀疏，配色与结构仍沿用模板定义。
\makeatletter
\let\huaweiPythonBegin\Python
\let\huaweiPythonEnd\endPython
\renewcommand{\Python}[1]{%
  \huaweiPythonBegin{#1}%
  \lstset{basicstyle=\scriptsize\ttfamily,xleftmargin=4pt,xrightmargin=4pt,framesep=2pt}%
}
\renewcommand{\endPython}{\huaweiPythonEnd}
\makeatother"""


def main() -> int:
    with io.open(MAIN, encoding="utf-8") as fh:
        s = fh.read()
    start = s.find("% 附录代码排版")
    if start == -1:
        raise SystemExit("未找到待替换的排版块")
    end = s.find("\\makeatother", start)
    if end == -1:
        raise SystemExit("未找到 makeatother 结束标记")
    end += len("\\makeatother")
    s = s[:start] + NEW + s[end:]
    with io.open(MAIN, "w", encoding="utf-8") as fh:
        fh.write(s)
    print("已收紧 Python 代码环境")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())