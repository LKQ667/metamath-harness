"""把附录净化代码内联进论文主稿的代码附录区。"""

from __future__ import annotations

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
TEX = BASE / "论文" / "main.tex"
APPENDIX = BASE / "论文" / "附录代码"
START = "% APPENDIX-CODE-START"
END = "% APPENDIX-CODE-END"
TITLES = {
    "prepare_data.py": "数据预处理与派生表生成",
    "envdata.py": "派生数据装载与参数索引",
    "cropmodel.py": "混合整数规划模型构建与求解",
    "solve_q1.py": "问题一求解主程序",
    "solve_q2.py": "问题二情景型随机规划主程序",
    "solve_q3.py": "问题三相关性建模主程序",
    "sensitivity.py": "灵敏度分析主程序",
    "collect_final_results.py": "唯一结果源汇总程序",
    "verify_core.py": "跨问核心复核程序",
}


def blocks() -> list[str]:
    parts: list[str] = []
    for path in sorted(APPENDIX.glob("*.py")):
        name = path.name
        title = TITLES.get(name, name)
        code = path.read_text(encoding="utf-8").rstrip("\n")
        replaced = name.replace("_", "\\_")
        parts.append(f"\\subsection{{{title}}}")
        parts.append("")
        parts.append(f"% 附录代码文件：论文/附录代码/{name}")
        parts.append("")
        parts.append(f"\\begin{{Python}}{{{replaced}}}")
        parts.append(code)
        parts.append("\\end{Python}")
        parts.append("")
    return parts


def main() -> int:
    text = TEX.read_text(encoding="utf-8")
    if START not in text or END not in text:
        print("缺少代码附录标记，无法内联")
        return 1
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    body = "\n".join(blocks())
    TEX.write_text(f"{head}{START}\n{body}\n{END}{tail}", encoding="utf-8")
    print(f"embedded {len(list(APPENDIX.glob('*.py')))} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
