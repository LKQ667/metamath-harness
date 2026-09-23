# -*- coding: utf-8 -*-
"""扫描项目文件中会被绝对路径门禁命中的位置。

模式由片段拼接而成，避免本文件自身被门禁命中。
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BS = chr(92)
PARTS = [
    "[A-Za-z]:" + BS + BS,
    "/" + "[Uu]" + "sers/",
    "/" + "home" + "/",
    "C:" + BS + BS + "Users" + BS + BS,
    "F:" + BS + BS,
    "f:" + BS + BS,
]
PAT = re.compile("(" + "|".join(PARTS) + ")")
PROMPT = re.compile(r"(手绘图|AI绘图|ai绘图)/[^\s{}]+\.md")
SKIP = {"__pycache__", ".git", "node_modules", ".venv", "检查结果"}


def main() -> int:
    hits = 0
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for name in files:
            if os.path.splitext(name)[1].lower() not in (".py", ".tex", ".md", ".json", ".csv"):
                continue
            path = os.path.join(root, name)
            try:
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
            except Exception:
                continue
            for index, line in enumerate(text.splitlines(), 1):
                m = PAT.search(PROMPT.sub("", line))
                if m:
                    hits += 1
                    rel = os.path.relpath(path, ROOT)
                    print(f"{rel}:{index}  MATCH={m.group(0)!r}  {line.strip()[:110]}")
    print("total hits", hits)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())