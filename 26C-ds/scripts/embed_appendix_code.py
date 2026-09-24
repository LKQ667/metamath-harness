"""把净化后的附录代码嵌入论文主稿，并同步附录代码文件路径标记。

对每个附录文件，替换 `\\begin{Python}{文件名}` 与 `\\end{Python}` 之间的全部内容，
因此可重复运行以同步最新净化代码。

运行：python scripts/embed_appendix_code.py
"""

from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True
try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
TEX = PROJECT / "论文" / "main.tex"
APPENDIX_DIR = PROJECT / "论文" / "附录代码"

FILES = ("eeg_lib.py", "preprocess_eeg.py", "solve_q1.py", "solve_q2.py", "solve_q3.py")


def collapse_blank_lines(code: str, max_run: int = 2) -> str:
    out: list[str] = []
    run = 0
    for line in code.splitlines():
        if line.strip():
            run = 0
            out.append(line.rstrip())
        else:
            run += 1
            if run <= max_run:
                out.append("")
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out)


def main() -> int:
    if not TEX.exists():
        print("缺少论文主文件")
        return 1
    text = TEX.read_text(encoding="utf-8")
    replaced = 0
    for filename in FILES:
        path = APPENDIX_DIR / filename
        if not path.exists():
            print(f"缺少净化代码文件: {path.relative_to(PROJECT).as_posix()}")
            return 1
        code = collapse_blank_lines(path.read_text(encoding="utf-8"))
        if "\\end{Python}" in code:
            print(f"代码中含 \\end{{Python}}，无法内联: {filename}")
            return 1
        escaped = filename.replace("_", "\\_")
        pattern = re.compile(
            r"(\\begin\{Python\}\{" + re.escape(escaped) + r"\}\n)(.*?)(\n\\end\{Python\})",
            re.DOTALL)
        match = pattern.search(text)
        if match is None:
            print(f"未找到 {filename} 的代码块")
            return 1
        text = text[:match.start(2)] + code + text[match.end(2):]
        replaced += 1
        marker = f"论文/附录代码/{filename}"
        heading = "\\subsection{" + escaped + "}"
        if marker not in text and heading in text:
            text = text.replace(heading, heading + f"\n\n% 净化代码文件：{marker}", 1)
    TEX.write_text(text, encoding="utf-8")
    print(f"已同步 {replaced} 个附录代码块")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
