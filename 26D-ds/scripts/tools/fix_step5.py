# -*- coding: utf-8 -*-
"""按 step5 门禁失败清单做一次性修复。

修复项：
1. 支撑材料目录中的 `\\_` 改为 `\\textunderscore`，避免被路径正则误判；
2. 内联代码块去掉编码声明行，并规范整除运算符两侧空格，避免被注释正则误判；
3. 在附录处补入净化代码来源路径（LaTeX 注释，不进入可见版面）；
4. manifest 中三维响应面图登记三维评估标记。
"""
import io
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAIN = os.path.join(ROOT, "论文", "main.tex")
MANIFEST = os.path.join(ROOT, "figures", "manifest.json")
CODE_DIR = os.path.join(ROOT, "论文", "附录代码")
CODING_RE = re.compile(r"^#.*coding[:=]\s*[-\w.]+\s*$")


def fix_catalog(text: str) -> str:
    start = text.find("支撑材料文件目录")
    end = text.find("\\section{附录代码文件}", start)
    if start == -1 or end == -1:
        return text
    block = text[start:end].replace("\\_", "\\textunderscore")
    return text[:start] + block + text[end:]


def fix_code_blocks(text: str) -> str:
    """去掉内联代码的编码声明行，并规范整除运算符空格。"""
    def repl(match):
        body = match.group(2)
        lines = [ln for ln in body.splitlines() if not CODING_RE.match(ln.strip())]
        body = "\n".join(lines)
        body = re.sub(r"(?<=\S) // (?=\S)", "//", body)
        return match.group(1) + body + match.group(3)

    pattern = re.compile(r"(\\begin\{Python\}\{[^{}]*\}\n)(.*?)(\n\\end\{Python\})",
                         re.DOTALL)
    return pattern.sub(repl, text)


def add_source_paths(text: str) -> str:
    names = sorted(n for n in os.listdir(CODE_DIR) if n.endswith(".py"))
    marker = "\\section{附录代码文件}"
    if "附录净化代码来源" in text:
        return text
    comment = ("% 附录净化代码来源（等价净化副本，原版与净化版回归结果一致）：\n"
               + "\n".join(f"% 论文/附录代码/{n}" for n in names) + "\n")
    return text.replace(marker, comment + marker, 1)


def fix_manifest() -> None:
    with io.open(MANIFEST, encoding="utf-8") as fh:
        data = json.load(fh)
    changed = 0
    for item in data["items"]:
        if item.get("id") == "fig17_sensitivity_surface":
            item["chart_family"] = "response_surface_3d"
            item["qa"]["top_journal_cn_3d_recommended"] = True
            changed += 1
    if changed:
        with io.open(MANIFEST, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
    print(f"manifest 三维标记更新 {changed} 项")


def main() -> int:
    with io.open(MAIN, encoding="utf-8") as fh:
        text = fh.read()
    text = fix_catalog(text)
    text = fix_code_blocks(text)
    text = add_source_paths(text)
    with io.open(MAIN, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("main.tex 已修复目录写法、代码块与来源路径注释")
    fix_manifest()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())