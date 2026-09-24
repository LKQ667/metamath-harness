"""重建论文附录的代码章节，把核心净化副本按固定顺序内联到模板 Python 代码环境中。"""
from __future__ import annotations

import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
TEX = PROJECT / "论文" / "main.tex"
APPENDIX = PROJECT / "论文" / "附录代码"

ENTRIES = (
    ("extract_features.py", "问题一三模态特征提取与时序对齐主脚本，含时间量化算子、区间聚合与文本哈希词袋表示。"),
    ("mm_data.py", "三模态数据接口与评价指标，含掩码反演、分位秩映射、缺失区间抽样与分类回归指标。"),
    ("model.py", "问题二鲁棒融合模型、消融变体、单模态编码器与编码序列生成。"),
    ("model_q3.py", "问题三三层可解释融合模型，含模态级注意力、位置级重要性与逐位置模态贡献。"),
)

SECTION_START = "\\section{附录代码文件}"
APPENDIX_END = "\\end{appendices}"


def build_section() -> str:
    lines = [SECTION_START, ""]
    for index, (filename, description) in enumerate(ENTRIES):
        source = APPENDIX / filename
        if not source.exists():
            raise SystemExit(f"缺少附录净化文件: {source}")
        code = source.read_text(encoding="utf-8").rstrip("\n")
        title = filename.replace("_", "\\_")
        lines.append(f"\\subsection{{{title}}}")
        lines.append("")
        lines.append(description)
        lines.append("")
        lines.append(f"净化副本文件：\\texttt{{\\detokenize{{论文/附录代码/{filename}}}}}")
        lines.append("")
        lines.append(f"\\begin{{Python}}{{{title}}}")
        lines.append(code)
        lines.append("\\end{Python}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    text = TEX.read_text(encoding="utf-8")
    start = text.find(SECTION_START)
    end = text.find(APPENDIX_END, start)
    if start == -1 or end == -1:
        raise SystemExit("无法定位附录代码章节")
    # 回退到“支撑材料文件目录”之后，避免误删目录内容
    rebuilt = text[:start] + build_section() + "\n" + text[end:]
    # 清理可能残留的占位符
    rebuilt = re.sub(r"(?m)^PLACEHOLDER_[A-Z0-9_]+$", "", rebuilt)
    TEX.write_text(rebuilt, encoding="utf-8")
    print(f"已重建附录代码章节，共 {len(ENTRIES)} 个代码块")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
