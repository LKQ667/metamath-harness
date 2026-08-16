#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查亚太杯中文赛数据台账与 Excel 数据簿。"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from common import project_arg, read_text, write_report


REQUIRED_MD_TOKENS = [
    "来源机构",
    "来源链接",
    "访问日期",
    "数据作用",
    "字段说明",
    "清洗记录",
]

REQUIRED_SHEETS = ["数据清单", "原始数据索引", "清洗后数据", "字段说明", "来源映射"]
URL_RE = re.compile(r"https?://[^\s)>\"]+")


def workbook_sheets(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("xl/workbook.xml")
    root = ET.fromstring(xml)
    ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    return [node.attrib.get("name", "") for node in root.findall(".//main:sheet", ns)]


def main() -> int:
    parser = project_arg("检查数据来源台账")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []

    data_dir = project / "数据"
    data_md = data_dir / "data.md"
    data_xlsx = data_dir / "data.xlsx"

    if not data_dir.exists():
        errors.append(f"缺少数据目录: {data_dir}")

    if not data_md.exists():
        errors.append(f"缺少数据来源台账: {data_md}")
    else:
        text = read_text(data_md)
        for token in REQUIRED_MD_TOKENS:
            if token not in text:
                errors.append(f"data.md 缺少栏目: {token}")
        if not URL_RE.search(text):
            errors.append("data.md 未发现可点击 URL")
        if "禁止编造" not in text and "不得把任何示例数值写入模型" not in text:
            errors.append("data.md 缺少禁止编造或待赛题数据说明")

    if not data_xlsx.exists():
        errors.append(f"缺少数据工作簿: {data_xlsx}")
    else:
        try:
            sheets = workbook_sheets(data_xlsx)
        except Exception as exc:
            errors.append(f"data.xlsx 解析失败: {exc}")
        else:
            for sheet in REQUIRED_SHEETS:
                if sheet not in sheets:
                    errors.append(f"data.xlsx 缺少工作表: {sheet}")

    return write_report(not errors, "check_data_sources", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
