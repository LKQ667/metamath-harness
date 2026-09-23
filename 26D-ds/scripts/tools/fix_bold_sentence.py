# -*- coding: utf-8 -*-
"""修正摘要中一处整体加粗的完整句：在粗体前补入承接词。"""
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAIN = os.path.join(ROOT, "论文", "main.tex")

OLD = "升至 0.273。" + chr(92) + "textbf{2 组分区在资源规模、冗余与均衡三方面均优于 3 组分区}。"
NEW = "升至 0.273，故" + chr(92) + "textbf{2 组分区在资源规模、冗余与均衡三方面均优于 3 组分区}。"


def main() -> int:
    with io.open(MAIN, encoding="utf-8") as fh:
        text = fh.read()
    count = text.count(OLD)
    if count == 0:
        print("未找到目标片段")
        return 0
    with io.open(MAIN, "w", encoding="utf-8") as fh:
        fh.write(text.replace(OLD, NEW))
    print(f"已修正 {count} 处整体加粗的完整句")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())