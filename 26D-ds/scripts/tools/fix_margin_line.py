# -*- coding: utf-8 -*-
"""把造成右边距越界的行内公式改写为可断行的中文表述。"""
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAIN = os.path.join(ROOT, "论文", "main.tex")

OLD = "研究单服务区直接往返 \\allowbreak O01$\\to$Si$\\to$O01 的运输能力与货箱组批"
NEW = "研究单服务区由调度中心 O01 直飞某一服务区再原路返回的运输能力与货箱组批"


def main() -> int:
    with io.open(MAIN, encoding="utf-8") as fh:
        text = fh.read()
    if OLD not in text:
        print("未找到目标句")
        return 0
    with io.open(MAIN, "w", encoding="utf-8") as fh:
        fh.write(text.replace(OLD, NEW))
    print("已改写为可断行表述")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())