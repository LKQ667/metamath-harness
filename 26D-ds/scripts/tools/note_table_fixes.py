# -*- coding: utf-8 -*-
"""在三轮自查中补记本次表格越界修复与数据表迁移。"""
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REVIEW = os.path.join(ROOT, "检查结果", "三轮自查.md")

ANCHOR = "### 支撑材料目录"

NOTE = """### 表格越界修复与数据表迁移

逐页用光栅化非白像素范围复核页面内容边界，发现并修复了两处表格越界：
“2 组与 3 组分区的任务组构成”与“2 组与 3 组分区在四个维度上的对比”两表原先使用定宽列，
最右列越出页面右边界约 17 pt；已改为按文本宽度自适应的 tabularx 列型，表内文字自动换行。
同时修复了一处行内公式造成的右边距越界，并补上了问题二算法缺失的交叉引用标签。
复核结果为全文最长文本行右端点 540.3 pt，与正文右文本边界一致，无越界行。

按“附录不计入正文页数”的口径，把正文中体量最大的两张纯数据表迁入附录：
“三种机型在各服务区的最大安全载荷”移入附录 A，“中继机队规模对联合调度可行性的影响”移入附录 C，
正文相应位置改为引用并保留关键数值与结论；附录 A 另补入“各服务区组批方案明细”表，
数据取自唯一结果源。附录数据表统一改为就地排版，使其落在所属附录小节内，
不再漂移到代码附录之间。正文因此由 34 页减为 33 页。

"""


def main() -> int:
    with io.open(REVIEW, encoding="utf-8") as fh:
        text = fh.read()
    if "表格越界修复与数据表迁移" in text:
        print("已存在该记录")
        return 0
    if ANCHOR not in text:
        raise SystemExit("未找到插入位置")
    text = text.replace(ANCHOR, NOTE + ANCHOR, 1)
    with io.open(REVIEW, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("已补记表格修复与迁移说明")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())