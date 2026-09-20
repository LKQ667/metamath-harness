#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pathlib import Path
from common import project_arg, read_text, write_report


SOURCE_TOKENS = ["doi", "http://", "https://", "GB/T", "ASTM", "ISBN", "出版社", "标准"]


def main() -> int:
    parser = project_arg("检查文献来源与 source_map.md")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    source_map = project / "文献" / "source_map.md"
    if not source_map.exists():
        errors.append(f"缺少文献来源映射: {source_map}")
    else:
        text = read_text(source_map)
        for token in ["来源链接", "可信等级", "支撑章节"]:
            if token not in text:
                errors.append(f"source_map.md 缺少字段: {token}")
    refs = list((project / "论文").rglob("*.tex")) if (project / "论文").exists() else []
    ref_text = "\n".join(read_text(p) for p in refs)
    if "\\bibitem" not in ref_text and "参考文献" not in ref_text:
        errors.append("论文中未发现参考文献")
    elif not any(token.lower() in ref_text.lower() for token in SOURCE_TOKENS):
        errors.append("参考文献缺少 DOI/URL/标准号/出版社等可追溯信息")
    return write_report(not errors, "check_bibliography_sources", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
