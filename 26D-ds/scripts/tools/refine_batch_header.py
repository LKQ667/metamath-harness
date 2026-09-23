# -*- coding: utf-8 -*-
"""精简新增组批明细表的表头，避免单元格内断词与括号密度上升。"""
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAIN = os.path.join(ROOT, "论文", "main.tex")

OLD = ("  服务区 & 架次数/架次 & 机型构成 & 运输能耗/kWh & 累计作业时间/s & "
       "最大安全载荷（C 型）/kg \\\\")
NEW = "  服务区 & 架次数 & 机型构成 & 能耗/kWh & 作业时间/s & C 型载荷/kg \\\\"


def main() -> int:
    with io.open(MAIN, encoding="utf-8") as fh:
        text = fh.read()
    if OLD not in text:
        print("未找到目标表头")
        return 0
    with io.open(MAIN, "w", encoding="utf-8") as fh:
        fh.write(text.replace(OLD, NEW))
    print("表头已精简")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())