# -*- coding: utf-8 -*-
"""为问题二算法补上缺失的 label，消除未定义交叉引用。"""
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAIN = os.path.join(ROOT, "论文", "main.tex")

OLD = ("\\caption{问题二分层构造与局部搜索算法}\n"
       "\\begin{algorithmic}[1]")
NEW = ("\\caption{问题二分层构造与局部搜索算法}\n"
       "\\label{alg:q2}\n"
       "\\begin{algorithmic}[1]")


def main() -> int:
    with io.open(MAIN, encoding="utf-8") as fh:
        text = fh.read()
    if "\\label{alg:q2}" in text:
        print("已存在 label")
        return 0
    if OLD not in text:
        raise SystemExit("未找到问题二算法环境")
    with io.open(MAIN, "w", encoding="utf-8") as fh:
        fh.write(text.replace(OLD, NEW))
    print("已补上 alg:q2 标签")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())