# -*- coding: utf-8 -*-
"""一次性数据探察脚本：导出全部附件表结构，供数据预处理与建模使用。

路径一律由公共数据层解析，脚本内不出现任何绝对路径。
"""
import glob
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common_d import BASIC_DIR  # noqa: E402

out_lines = []


def emit(text=""):
    out_lines.append(str(text))


for f in sorted(glob.glob(os.path.join(BASIC_DIR, "*.xlsx"))):
    emit("=" * 100)
    emit(os.path.basename(f))
    xl = pd.ExcelFile(f)
    emit("sheets: %s" % xl.sheet_names)
    for sh in xl.sheet_names:
        df = xl.parse(sh, header=None)
        emit("-" * 80)
        emit("[sheet] %s  shape=%s" % (sh, df.shape))
        emit(df.head(40).to_string(max_colwidth=26))

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inspect_data.txt")
with open(out, "w", encoding="utf-8") as fh:
    fh.write("\n".join(out_lines))
print("written", os.path.basename(out), len(out_lines), "lines")