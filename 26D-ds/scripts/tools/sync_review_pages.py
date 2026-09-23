# -*- coding: utf-8 -*-
"""同步三轮自查中的正文边界页码与页数结论。"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REVIEW = os.path.join(ROOT, "检查结果", "三轮自查.md")
AUX = os.path.join(ROOT, "论文", "main.aux")


def page_of(aux: str, key: str):
    m = re.search(r"newlabel\{" + key + r"\}\{\{[^}]*\}\{(\d+)\}", aux)
    return int(m.group(1)) if m else None


def main() -> int:
    with io.open(AUX, encoding="utf-8", errors="replace") as fh:
        aux = fh.read()
    start = page_of(aux, "body:start")
    end = page_of(aux, "body:end")
    app = page_of(aux, "appendix:start")
    pages = end - start + 1
    with io.open(REVIEW, encoding="utf-8") as fh:
        text = fh.read()
    text = re.sub(r"- 正文起始页：\d+", f"- 正文起始页：{start}", text)
    text = re.sub(r"- 正文结束页：\d+", f"- 正文结束页：{end}", text)
    text = re.sub(r"- 附录起始页：\d+", f"- 附录起始页：{app}", text)
    text = re.sub(r"- 正文实际页数：\d+", f"- 正文实际页数：{pages}", text)
    text = text.replace("`body:end` 位于第 34 页", f"`body:end` 位于第 {end} 页")
    text = text.replace("`appendix:start` 位于第 35 页", f"`appendix:start` 位于第 {app} 页")
    text = text.replace("正文实际页数 34 页", f"正文实际页数 {pages} 页")
    with io.open(REVIEW, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"三轮自查已同步：正文 {start}-{end}（{pages} 页），附录起始 {app}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())